from typing import List, Tuple

import torch
from torch import Tensor
import torch.nn as nn
import torch.nn.functional as F
import snntorch as snn

from config import ModelParameters, TrainingParameters
from utils import Utilities


# Define a different network
class ScnnNet(nn.Module):
    def __init__(
        self,
        res: int = ModelParameters.RESOLUTION,
        spike_grad: float = ModelParameters.SPIKE_GRADIENT,
        beta: float = ModelParameters.BETA,
        batch_size: int = TrainingParameters.BATCH_SIZE,
        num_steps: int = ModelParameters.NUM_STEPS,
        conv_kernel_size: int = ModelParameters.CONV_KERNEL_SIZE,
        conv_padding_size: int = ModelParameters.CONV_PADDING_SIZE,
        conv_stride: int = ModelParameters.CONV_STRIDE,
        mp_kernel_size: int = ModelParameters.MP_KERNEL_SIZE,
        mp_padding: int = ModelParameters.MP_PADDING_SIZE,
        mp_stride_length: int = ModelParameters.MP_STRIDE_LENGTH,
        dropout: float = ModelParameters.DROPOUT,
        num_hidden: int = ModelParameters.NUM_HIDDEN,
        num_outputs: int = ModelParameters.NUM_OUTPUTS,
    ):
        super().__init__()

        self.res = res
        self.spike_grad = spike_grad
        self.beta = beta
        self.batch_size = batch_size
        self.num_steps = num_steps
        self.conv_kernel_size = conv_kernel_size
        self.conv_padding_size = conv_padding_size
        self.conv_stride = conv_stride
        self.mp_kernel_size = mp_kernel_size
        self.mp_padding = mp_padding
        self.mp_stride_length = mp_stride_length
        self.dropout = dropout
        self.num_hidden = num_hidden
        self.num_outputs = num_outputs

        self.output_sizes: List[int] = Utilities.get_output_sizes(
            self.res,
            self.conv_kernel_size,
            self.conv_padding_size,
            self.conv_stride,
            self.mp_kernel_size,
            self.mp_padding,
            self.mp_stride_length,
        )
        # Do I change channels to a variable incase I end up with RGB images? ## Padding = 0 as all information is at the centre of image (may change if lower resolution)
        self.conv1 = nn.Conv2d(
            in_channels=1,
            out_channels=64,
            kernel_size=self.conv_kernel_size,
            padding=self.conv_padding_size,
        )
        self.mp1 = nn.MaxPool2d(
            kernel_size=self.mp_kernel_size, stride=self.mp_stride_length
        )
        self.lif1 = snn.Leaky(beta=self.beta, spike_grad=self.spike_grad)

        self.conv2 = nn.Conv2d(
            in_channels=64,
            out_channels=128,
            kernel_size=self.conv_kernel_size,
            padding=self.conv_padding_size,
        )
        self.lif2 = snn.Leaky(beta=self.beta, spike_grad=self.spike_grad)

        self.conv3 = nn.Conv2d(
            in_channels=128,
            out_channels=128,
            kernel_size=self.conv_kernel_size,
            padding=self.conv_padding_size,
        )
        self.mp2 = nn.MaxPool2d(
            kernel_size=self.mp_kernel_size, stride=self.mp_stride_length
        )
        self.lif3 = snn.Leaky(beta=self.beta, spike_grad=self.spike_grad)

        self.conv4 = nn.Conv2d(
            in_channels=128,
            out_channels=256,
            kernel_size=self.conv_kernel_size,
            padding=self.conv_padding_size,
        )
        self.lif4 = snn.Leaky(beta=self.beta, spike_grad=self.spike_grad)

        self.conv5 = nn.Conv2d(
            in_channels=256,
            out_channels=256,
            kernel_size=self.conv_kernel_size,
            padding=self.conv_padding_size,
        )
        self.maxpool = nn.MaxPool2d(
            kernel_size=self.mp_kernel_size, stride=self.mp_stride_length
        )
        self.lif5 = snn.Leaky(beta=self.beta, spike_grad=self.spike_grad)

        self.drop1 = nn.Dropout(self.dropout)

        self.fc1 = nn.Linear(
            256 * self.output_sizes[-1] * self.output_sizes[-1], self.num_hidden
        )
        self.lif6 = snn.Leaky(beta=self.beta, spike_grad=self.spike_grad)
        self.drop2 = nn.Dropout(self.dropout)

        self.fc2 = nn.Linear(self.num_hidden, self.num_hidden)
        self.lif7 = snn.Leaky(beta=self.beta, spike_grad=self.spike_grad)

        self.fc3 = nn.Linear(self.num_hidden, self.num_outputs)
        self.lif8 = snn.Leaky(beta=self.beta, spike_grad=self.spike_grad)

    def forward(self, x: Tensor) -> Tuple[torch.Tensor, torch.Tensor]:

        mem1 = self.lif1.init_leaky()
        mem2 = self.lif2.init_leaky()
        mem3 = self.lif3.init_leaky()
        mem4 = self.lif4.init_leaky()

        mem5 = self.lif5.init_leaky()

        mem6 = self.lif6.init_leaky()
        mem7 = self.lif7.init_leaky()

        mem8 = self.lif8.init_leaky()

        spk8_rec = []
        mem8_rec = []

        # Reshape x to be (num_steps, batch_size, channels, height, width)
        x = x.view(self.num_steps, self.batch_size, 1, self.res, self.res)

        for step in range(self.num_steps):
            cur1 = self.mp1(self.conv1(x[step]))
            spk1, mem1 = self.lif1(cur1, mem1)

            cur2 = self.conv2(spk1)
            spk2, mem2 = self.lif2(cur2, mem2)
            cur3 = self.conv3(spk2)
            cur3 = self.mp2(cur3)
            spk3, mem3 = self.lif3(cur3, mem3)

            cur4 = self.conv4(spk3)
            spk4, mem4 = self.lif4(cur4, mem4)
            cur5 = self.conv5(spk4)
            cur5 = self.maxpool(cur5)
            spk5, mem5 = self.lif5(cur5, mem5)

            spk5 = self.drop1(spk5)
            cur6 = self.fc1(spk5.view(self.batch_size, -1))
            spk6, mem6 = self.lif6(cur6, mem6)

            spk6 = self.drop2(spk6)
            cur7 = self.fc2(spk6)
            spk7, mem7 = self.lif7(cur7, mem7)

            cur8 = self.fc3(spk7)
            spk8, mem8 = self.lif8(cur8, mem8)

            spk8_rec.append(spk8)
            mem8_rec.append(mem8)

        return torch.stack(spk8_rec, dim=0), torch.stack(mem8_rec, dim=0)
