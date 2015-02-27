# -*- coding: utf-8 -*-
#!/usr/bin/env python
#
# Copyright 2012-2015 BigML
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""An local Ensemble object.

This module defines an Ensemble to make predictions locally using its
associated models.

This module can not only save you a few credits, but also enormously
reduce the latency for each prediction and let you use your models
offline.

from bigml.api import BigML
from bigml.ensemble import Ensemble

# api connection
api = BigML(storage='./storage')

# creating ensemble
ensemble = api.create_ensemble('dataset/5143a51a37203f2cf7000972')

# Ensemble object to predict
ensemble = Ensemble(ensemble, api)
ensemble.predict({"petal length": 3, "petal width": 1})

"""
import sys
import logging
import gc
import json
LOGGER = logging.getLogger('BigML')

from bigml.api import BigML, get_ensemble_id, get_model_id, check_resource
from bigml.model import Model, retrieve_resource, print_distribution
from bigml.model import STORAGE, ONLY_MODEL, LAST_PREDICTION
from bigml.multivote import MultiVote
from bigml.multivote import PLURALITY_CODE
from bigml.multimodel import MultiModel
from bigml.basemodel import BaseModel, print_importance


class Ensemble(object):
    """A local predictive Ensemble.

       Uses a number of BigML remote models to build an ensemble local version
       that can be used to generate predictions locally.
       The expected arguments are:

       ensemble: ensemble object or id, list of model objects or
                 ids or list of local model objects (see Model)
       api: connection object. If None, a new connection object is
            instantiated.
       max_models: integer that limits the number of models instantiated and
                   held in memory at the same time while predicting. If None,
                   no limit is set and all the ensemble models are
                   instantiated and held in memory permanently.
    """

    def __init__(self, ensemble, api=None, max_models=None):

        if api is None:
            self.api = BigML(storage=STORAGE)
        else:
            self.api = api
        self.resource_id = None
        # to be deprecated
        self.ensemble_id = None
        self.objective_id = None
        self.distributions = None
        self.models_splits = []
        self.multi_model = None
        if isinstance(ensemble, list):
            if all([isinstance(model, Model) for model in ensemble]):
                models = ensemble
                self.model_ids = [local_model.resource_id for local_model in
                                  models]
            else:
                try:
                    models = [get_model_id(model) for model in ensemble]
                    self.model_ids = models
                except ValueError, exc:
                    raise ValueError('Failed to verify the list of models.'
                                     ' Check your model id values: %s' %
                                     str(exc))
            self.distributions = None
        else:
            ensemble = self.get_ensemble_resource(ensemble)
            self.resource_id = get_ensemble_id(ensemble)
            self.ensemble_id = self.resource_id
            ensemble = retrieve_resource(self.api, self.resource_id)
            models = ensemble['object']['models']
            self.distributions = ensemble['object'].get('distributions', None)
            self.model_ids = models

        number_of_models = len(models)
        if max_models is None:
            self.models_splits = [models]
        else:
            self.models_splits = [models[index:(index + max_models)] for index
                                  in range(0, number_of_models, max_models)]
        if len(self.models_splits) == 1:
            if not isinstance(models[0], Model):
                models = [retrieve_resource(self.api, model_id,
                                            query_string=ONLY_MODEL)
                          for model_id in self.models_splits[0]]
            self.multi_model = MultiModel(models, self.api)
        self.fields, self.objective_id = self.all_model_fields()

    def get_ensemble_resource(self, ensemble):
        """Extracts the ensemble resource info. The ensemble argument can be
           - a path to a local file
           - an ensemble id
        """
        # the string can be a path to a JSON file
        if isinstance(ensemble, basestring):
            try:
                with open(ensemble) as ensemble_file:
                    ensemble = json.load(ensemble_file)
                    self.resource_id = get_ensemble_id(ensemble)
                    if self.resource_id is None:
                        raise ValueError("The JSON file does not seem"
                                         " to contain a valid BigML ensemble"
                                         " representation.")
            except IOError:
                # if it is not a path, it can be an ensemble id
                self.resource_id = get_ensemble_id(ensemble)
                if self.resource_id is None:
                    if ensemble.find('ensemble/') > -1:
                        raise Exception(
                            api.error_message(ensemble,
                                              resource_type='ensemble',
                                              method='get'))
                    else:
                        raise IOError("Failed to open the expected JSON file"
                                      " at %s" % ensemble)
            except ValueError:
                raise ValueError("Failed to interpret %s."
                                 " JSON file expected.")
        return ensemble

    def list_models(self):
        """Lists all the model/ids that compound the ensemble.

        """
        return self.model_ids

    def predict(self, input_data, by_name=True, method=PLURALITY_CODE,
                with_confidence=False, add_confidence=False,
                add_distribution=False, add_count=False, add_median=False,
                options=None, missing_strategy=LAST_PREDICTION):
        """Makes a prediction based on the prediction made by every model.

           The method parameter is a numeric key to the following combination
           methods in classifications/regressions:
              0 - majority vote (plurality)/ average: PLURALITY_CODE
              1 - confidence weighted majority vote / error weighted:
                  CONFIDENCE_CODE
              2 - probability weighted majority vote / average:
                  PROBABILITY_CODE
              3 - threshold filtered vote / doesn't apply:
                  THRESHOLD_CODE
        """

        if len(self.models_splits) > 1:
            # If there's more than one chunck of models, they must be
            # sequentially used to generate the votes for the prediction
            votes = MultiVote([])
            for models_split in self.models_splits:
                if not isinstance(models_split[0], Model):
                   models = [retrieve_resource(self.api, model_id,
                                                query_string=ONLY_MODEL)
                             for model_id in models_split]
                multi_model = MultiModel(models, api=self.api)
                votes_split = multi_model.generate_votes(
                    input_data, by_name=by_name,
                    missing_strategy=missing_strategy,
                    add_median=add_median)
                votes.extend(votes_split.predictions)
        else:
            # When only one group of models is found you use the
            # corresponding multimodel to predict
            votes_split = self.multi_model.generate_votes(
                input_data, by_name=by_name, missing_strategy=missing_strategy,
                add_median=add_median)
            votes = MultiVote(votes_split.predictions)
        return votes.combine(method=method, with_confidence=with_confidence,
                             add_confidence=add_confidence,
                             add_distribution=add_distribution,
                             add_count=add_count,
                             add_median=add_median,
                             options=options)

    def field_importance_data(self):
        """Computes field importance based on the field importance information
           of the individual models in the ensemble.

        """
        field_importance = {}
        field_names = {}
        if (self.distributions is not None and
                isinstance(self.distributions, list) and
                all('importance' in item for item in self.distributions)):
            # Extracts importance from ensemble information
            importances = [model_info['importance'] for model_info in
                           self.distributions]
            for index in range(0, len(importances)):
                model_info = importances[index]
                for field_info in model_info:
                    field_id = field_info[0]
                    if not field_id in field_importance:
                        field_importance[field_id] = 0.0
                        name = self.fields[field_id]['name']
                        field_names[field_id] = {'name': name}
                    field_importance[field_id] += field_info[1]
        else:
            # Old ensembles, extracts importance from model information
            for model_id in self.model_ids:
                local_model = BaseModel(model_id, api=self.api)
                for field_info in local_model.field_importance:
                    field_id = field_info[0]
                    if not field_info[0] in field_importance:
                        field_importance[field_id] = 0.0
                        name = self.fields[field_id]['name']
                        field_names[field_id] = {'name': name}
                    field_importance[field_id] += field_info[1]

        number_of_models = len(self.model_ids)
        for field_id in field_importance.keys():
            field_importance[field_id] /= number_of_models
        return map(list, sorted(field_importance.items(), key=lambda x: x[1],
                                reverse=True)), field_names

    def print_importance(self, out=sys.stdout):
        """Prints ensemble field importance

        """
        print_importance(self, out=out)

    def get_data_distribution(self, distribution_type="training"):
        """Returns the required data distribution by adding the distributions
           in the models

        """
        ensemble_distribution = []
        categories = []
        for model_distribution in self.distributions:
            summary = model_distribution[distribution_type]
            if 'bins' in summary:
                distribution = summary['bins']
            elif 'counts' in summary:
                distribution = summary['counts']
            elif 'categories' in summary:
                distribution = summary['categories']
            for point, instances in distribution:
                if point in categories:
                    ensemble_distribution[
                        categories.index(point)][1] += instances
                else:
                    categories.append(point)
                    ensemble_distribution.append([point, instances])

        return sorted(ensemble_distribution, key=lambda x: x[0])

    def summarize(self, out=sys.stdout):
        """Prints ensemble summary. Only field importance at present.

        """
        distribution = self.get_data_distribution("training")

        out.write(u"Data distribution:\n")
        print_distribution(distribution, out=out)
        out.write(u"\n\n")

        predictions = self.get_data_distribution("predictions")

        out.write(u"Predicted distribution:\n")
        print_distribution(predictions, out=out)
        out.write(u"\n\n")

        out.write(u"Field importance:\n")
        self.print_importance(out=out)
        out.flush()

    def all_model_fields(self):
        """Retrieves the fields used as predictors in all the ensemble
           models

        """

        fields = {}
        models = []
        objective_id = None
        no_objective_id = False
        if isinstance(self.models_splits[0][0], Model):
            for split in self.models_splits:
                models.extend(split)
        else:
            models = self.model_ids
        for model_id in models:
            if isinstance(model_id, Model):
                local_model = model_id
            else:
                local_model = Model(model_id, self.api)
            gc.collect()
            fields.update(local_model.fields)
            if (objective_id is not None and
                    objective_id != local_model.objective_id):
                # the models' objective field have different ids, no global id
                no_objective_id = True
            else:
                objective_id = local_model.objective_id
        if no_objective_id:
            objective_id = None
        return fields, objective_id
