#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2021 Intel Corporation
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

import unittest
import sys
import torch
import torch.nn as nn
import numpy as np
import os
import shutil
from intel_extension_for_transformers.llm.runtime.deprecated.compile import compile
from intel_extension_for_transformers.llm.runtime.deprecated.compile.graph import Graph

file_name = os.path.splitext(os.path.basename(__file__))[0]

class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.wte = nn.Embedding(100, 256)

    def forward(self, input_ids):
        input_shape = input_ids.size()
        input_ids = input_ids.view(-1, input_shape[-1])
        inputs_embeds = self.wte(input_ids)
        return inputs_embeds

class TestTorchOP(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        pass

    @classmethod
    def tearDownClass(self):
        pass

    def test_1(self):
        n = Net()
        example_in = torch.ones(1, 32).long()
        traced_model = torch.jit.trace(n, example_in)
        torch.jit.save(traced_model, '{}.pt'.format(file_name))
        ref_out = traced_model(example_in).squeeze(0).detach().numpy()

        graph = compile('{}.pt'.format(file_name))
        graph.save(file_name)
        newgraph = Graph()
        newgraph.graph_init(file_name + '/conf.yaml', file_name + '/model.bin')
        out = newgraph.inference([example_in.numpy()])

        np.testing.assert_almost_equal(ref_out, [*out.values()][0], decimal=5)
        os.remove('{}.pt'.format(file_name))
        shutil.rmtree(file_name)

if __name__ == "__main__":
    unittest.main()
