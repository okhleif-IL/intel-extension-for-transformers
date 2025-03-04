#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import json
import logging
from collections import OrderedDict
from intel_extension_for_transformers.transformers import OptimizedModel
from intel_extension_for_transformers.transformers.utils.utility import LazyImport
from transformers import T5Config, MT5Config
from typing import Union, Optional
from .utils import get_module_path
from .optimized_sentence_transformers import OptimzedTransformer

sentence_transformers = LazyImport("sentence_transformers")
InstructorEmbedding = LazyImport("InstructorEmbedding")

logger = logging.getLogger(__name__)

class OptimizedInstructorTransformer(InstructorEmbedding.INSTRUCTOR_Transformer):
    def __init__(self, *args, **kwargs):
        """Initialize the OptimizedInstructorTransformer."""
        super().__init__(*args, **kwargs)

    def _load_model(self, model_name_or_path, config, cache_dir, **model_args):
        """Loads the transformer model"""
        if isinstance(config, T5Config):
            self._load_t5_model(model_name_or_path, config, cache_dir, **model_args)
        elif isinstance(config, MT5Config):
            self._load_mt5_model(model_name_or_path, config, cache_dir, **model_args)
        else:
            self.auto_model = OptimizedModel.from_pretrained(model_name_or_path,
                                                             config=config,
                                                             cache_dir=cache_dir,
                                                             **model_args)

class OptimizedInstructor(InstructorEmbedding.INSTRUCTOR):
    def __init__(self, *args, **kwargs):
        """Initialize the OptimizedInstructor."""
        super().__init__(*args, **kwargs)

    def _load_auto_model(self,
                         model_name_or_path,
                         token: Optional[Union[bool, str]],
                         cache_folder: Optional[str],
                         trust_remote_code: bool = False): # pragma: no cover
        """Creates a simple Transformer + Mean Pooling model and returns the modules."""
        logger.warning("No sentence-transformers model found with name {}." \
                       "Creating a new one with MEAN pooling.".format(model_name_or_path))
        transformer_model = OptimzedTransformer(
            model_name_or_path, cache_dir=cache_folder, model_args={"token": token,
                                                                    "trust_remote_code": trust_remote_code})
        pooling_model = sentence_transformers.models.Pooling(
            transformer_model.get_word_embedding_dimension(), 'mean')
        return [transformer_model, pooling_model]

    def _load_sbert_model(self,
                          model_name_or_path: str,
                          token: Optional[Union[bool, str]],
                          cache_folder: Optional[str],
                          trust_remote_code: bool = False):
        """Loads a full sentence-transformers model."""
        # Check if the config_sentence_transformers.json file exists (exists since v2 of the framework)
        config_sentence_transformers_json_path = sentence_transformers.util.load_file_path(
            model_name_or_path, 'config_sentence_transformers.json', token=token, cache_folder=cache_folder)
        if config_sentence_transformers_json_path is not None:
            with open(config_sentence_transformers_json_path) as fIn:
                self._model_config = json.load(fIn)

            if '__version__' in self._model_config and \
                'sentence_transformers' in self._model_config['__version__'] and \
                    self._model_config['__version__']['sentence_transformers'] > sentence_transformers.__version__:
                logger.warning("You try to use a model that was created with version {}, "\
                               "however, your version is {}. This might cause unexpected "\
                               "behavior or errors. In that case, try to update to the "\
                               "latest version.\n\n\n".format(
                                    self._model_config['__version__']['sentence_transformers'],
                                    sentence_transformers.__version__))

        # Check if a readme exists
        model_card_path = sentence_transformers.util.load_file_path(
            model_name_or_path, 'README.md', token=token, cache_folder=cache_folder)
        if model_card_path is not None:
            try:
                with open(model_card_path, encoding='utf8') as fIn:
                    self._model_card_text = fIn.read()
            except:
                pass

        # Load the modules of sentence transformer
        modules_json_path = sentence_transformers.util.load_file_path(
            model_name_or_path, 'modules.json', token=token, cache_folder=cache_folder)
        with open(modules_json_path) as fIn:
            modules_config = json.load(fIn)

        modules = OrderedDict()
        for module_config in modules_config:
            if module_config['idx']==0:
                logger.info('load Optimized InstructorTransformer')
                kwargs = {}
                for config_name in ['sentence_bert_config.json', 'sentence_roberta_config.json',
                                    'sentence_distilbert_config.json', 'sentence_camembert_config.json',
                                    'sentence_albert_config.json', 'sentence_xlm-roberta_config.json',
                                    'sentence_xlnet_config.json']:
                    config_path = sentence_transformers.util.load_file_path(
                        model_name_or_path, config_name, token=token, cache_folder=cache_folder)
                    if config_path is not None:
                        with open(config_path) as fIn:
                            kwargs = json.load(fIn)
                        break
                if "model_args" in kwargs:
                    kwargs["model_args"]["token"] = token
                    kwargs["model_args"]["trust_remote_code"] = trust_remote_code
                else:
                    kwargs["model_args"] = {"token": token, "trust_remote_code": trust_remote_code}
                module = OptimizedInstructorTransformer(model_name_or_path, cache_dir=cache_folder, **kwargs)
            elif module_config['idx']==1:
                module_class = InstructorEmbedding.INSTRUCTOR_Pooling
                module_path = get_module_path(
                    model_name_or_path, module_config['path'], token, cache_folder)
                module = module_class.load(module_path)
            else:
                module_class = InstructorEmbedding.import_from_string(module_config['type'])
                module_path = get_module_path(
                    model_name_or_path, module_config['path'], token, cache_folder)
                module = module_class.load(module_path)
            modules[module_config['name']] = module

        return modules
