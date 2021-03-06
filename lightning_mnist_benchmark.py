# -*- coding: utf-8 -*-
"""lightning_mnist_benchmark.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1ZZW2dmq8gdODCOgaCY8SkW_LSRxWPKSD

# Script to benchmark training using MNIST

The data augmentation applied with `torchvision` and `kornia`.

"""## Import needed libraries"""

#! Needed for Pytorch-Lightning profiling
import logging
logging.basicConfig(level=logging.INFO)

import os
import numpy as np

import torch
import torch.nn as nn
from torch.nn import functional as F
from torch.utils.data import DataLoader
from torchvision.datasets import MNIST
import torchvision as T

import pytorch_lightning as pl
import kornia as K

"""## Define CNN Model"""

class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, 3, 1)
        self.conv2 = nn.Conv2d(32, 64, 3, 1)
        self.dropout1 = nn.Dropout2d(0.25)
        self.dropout2 = nn.Dropout2d(0.5)
        self.fc1 = nn.Linear(9216, 128)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.conv1(x)
        x = F.relu(x)
        x = self.conv2(x)
        x = F.relu(x)
        x = F.max_pool2d(x, 2)
        x = self.dropout1(x)
        x = torch.flatten(x, 1)
        x = self.fc1(x)
        x = F.relu(x)
        x = self.dropout2(x)
        x = self.fc2(x)
        output = F.log_softmax(x, dim=1)
        return output

"""## Define lightning model"""

class CoolSystem(pl.LightningModule):

    def __init__(self, batch_size: int =32, augmentation_backend: str = 'kornia'):
        super(CoolSystem, self).__init__()
        self._batch_size: int = batch_size

        self.model = Net()

        if augmentation_backend == 'kornia':
            self.augmentation = torch.nn.Sequential(
                K.augmentation.RandomAffine(
                    [-45., 45.], [0., 0.5], [0.5, 1.5], [0., 0.5]
                ),
                K.color.Normalize(0.1307, 0.3081),
            )
            self.transform = lambda x: K.image_to_tensor(np.array(x)).float() / 255.

        elif augmentation_backend == 'torchvision':
            self.augmentation = None
            self.transform = T.transforms.Compose([
                T.transforms.RandomAffine(
                    [-45., 45.], [0., 0.5], [0.5, 1.5], [0., 0.5]
                ),
                T.transforms.ToTensor(),
                T.transforms.Normalize((0.1307,), (0.3081,)),
            ])
        else:
            raise ValueError(f"Unsupported backend: {augmentation_backend}")

    def forward(self, x):
        return self.model(x)

    def training_step(self, batch, batch_idx):
        # REQUIRED
        x, y = batch
        if self.augmentation is not None:
            with torch.no_grad():
                x = self.augmentation(x)  # => we perform GPU/Batched data augmentation
        y_hat = self.forward(x)
        loss = F.nll_loss(y_hat, y)
        tensorboard_logs = {'train_loss': loss}
        return {'loss': loss, 'log': tensorboard_logs}

    def configure_optimizers(self):
        # REQUIRED
        # can return multiple optimizers and learning_rate schedulers
        # (LBFGS it is automatically supported, no need for closure function)
        return torch.optim.Adam(self.parameters(), lr=0.0004)

    def prepare_data(self):
        MNIST(os.getcwd(), train=True, download=True, transform=self.transform)
        MNIST(os.getcwd(), train=False, download=True, transform=self.transform)

    def train_dataloader(self):
        # REQUIRED
        dataset = MNIST(os.getcwd(), train=True, download=False, transform=self.transform)
        loader = DataLoader(dataset, batch_size=self._batch_size, num_workers=os.cpu_count())
        return loader

"""## Run training"""

from pytorch_lightning import Trainer

devices = ['cpu', 'gpu']

backends = ['kornia', 'torchvision']

batch_sizes = [16, 32, 64, 128, 256, 512, 1028, 2048]

from collections import defaultdict
results_dict = defaultdict(dict)

for device in devices:
    results_dict[device] = {}
    for backend in backends:
        results_dict[device][backend] = {}
        for batch_size in batch_sizes:
            num_gpus: int  = 0 if device == 'cpu' else 1

            model = CoolSystem(batch_size=batch_size, augmentation_backend=backend)

            # most basic trainer, uses good defaults
            prof = pl.profiler.SimpleProfiler()
            trainer = Trainer(profiler=prof, max_epochs=1, gpus=num_gpus)
            trainer.fit(model)

            # sum results

            elapsed_time: float = 0.
            for (key, val) in prof.recorded_durations.items():
                elapsed_time += sum(val)

            print(f"## Training device: {device} / backend: {backend} / batch_size: {batch_size} took: {elapsed_time} (s)")
            results_dict[device][backend][batch_size] = elapsed_time

# print
print(results_dict)
for device, v1 in results_dict.items():
    for backend, v2 in v1.items():
        out_stream: str = f"{backend}-{device}"
        for batch_size, elapsed_time in v2.items():
            out_stream += f"\n{elapsed_time}"
        print(out_stream)
        print("########")   
