# -*- coding: utf-8 -*-
#!/usr/bin/env python
#
# Copyright 2015 BigML
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


""" Creating model on lists of datasets

"""
from world import world, setup_module, teardown_module
import create_source_steps as source_create
import create_dataset_steps as dataset_create
import create_model_steps as model_create
import create_multimodel_steps as multimodel_create 

class TestMultimodel(object):
        
    def test_scenario1(self):
        """
            Scenario: Successfully creating a model from a dataset list:
                Given I create a data source uploading a "<data>" file
                And I wait until the source is ready less than <time_1> secs
                And I create a dataset
                And I wait until the dataset is ready less than <time_2> secs
                And I store the dataset id in a list
                And I create a dataset
                And I wait until the dataset is ready less than <time_3> secs
                And I store the dataset id in a list
                Then I create a model from a dataset list
                And I wait until the model is ready less than <time_4> secs
                And I check the model stems from the original dataset list

                Examples:
                | data                | time_1  | time_2 | time_3 |  time_4 | 
                | ../data/iris.csv | 10      | 10     | 10     |  10
        """
        print self.test_scenario1.__doc__
        examples = [
            ['data/iris.csv', '10', '10', '10', '10']]
        for example in examples:
            print "\nTesting with:\n", example
            source_create.i_upload_a_file(self, example[0])
            source_create.the_source_is_finished(self, example[1])
            dataset_create.i_create_a_dataset(self)
            dataset_create.the_dataset_is_finished_in_less_than(self, example[2])
            multimodel_create.i_store_dataset_id(self)
            dataset_create.i_create_a_dataset(self)
            dataset_create.the_dataset_is_finished_in_less_than(self, example[3])
            multimodel_create.i_store_dataset_id(self)
            model_create.i_create_a_model_from_dataset_list(self)
            model_create.the_model_is_finished_in_less_than(self, example[4])
            multimodel_create.i_check_model_datasets_and_datasets_ids(self)
