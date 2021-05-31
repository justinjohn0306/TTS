import copy
import os
import unittest

import torch
from torch import nn, optim

from tests import get_tests_input_path
from TTS.tts.configs import Tacotron2Config
from TTS.tts.layers.losses import MSELossMasked
from TTS.tts.models.tacotron2 import Tacotron2
from TTS.utils.audio import AudioProcessor

# pylint: disable=unused-variable

torch.manual_seed(1)
use_cuda = torch.cuda.is_available()
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

c = Tacotron2Config()

ap = AudioProcessor(**c.audio)
WAV_FILE = os.path.join(get_tests_input_path(), "example_1.wav")


class TacotronTrainTest(unittest.TestCase):
    def test_train_step(self):  # pylint: disable=no-self-use
        input_dummy = torch.randint(0, 24, (8, 128)).long().to(device)
        input_lengths = torch.randint(100, 128, (8,)).long().to(device)
        input_lengths = torch.sort(input_lengths, descending=True)[0]
        mel_spec = torch.rand(8, 30, c.audio["num_mels"]).to(device)
        mel_postnet_spec = torch.rand(8, 30, c.audio["num_mels"]).to(device)
        mel_lengths = torch.randint(20, 30, (8,)).long().to(device)
        mel_lengths[0] = 30
        stop_targets = torch.zeros(8, 30, 1).float().to(device)
        speaker_ids = torch.randint(0, 5, (8,)).long().to(device)

        for idx in mel_lengths:
            stop_targets[:, int(idx.item()) :, 0] = 1.0

        stop_targets = stop_targets.view(input_dummy.shape[0], stop_targets.size(1) // c.r, -1)
        stop_targets = (stop_targets.sum(2) > 0.0).unsqueeze(2).float().squeeze()

        criterion = MSELossMasked(seq_len_norm=False).to(device)
        criterion_st = nn.BCEWithLogitsLoss().to(device)
        model = Tacotron2(num_chars=24, r=c.r, num_speakers=5).to(device)
        model.train()
        model_ref = copy.deepcopy(model)
        count = 0
        for param, param_ref in zip(model.parameters(), model_ref.parameters()):
            assert (param - param_ref).sum() == 0, param
            count += 1
        optimizer = optim.Adam(model.parameters(), lr=c.lr)
        for i in range(5):
            outputs = model.forward(
                input_dummy, input_lengths, mel_spec, mel_lengths, cond_input={"speaker_ids": speaker_ids}
            )
            assert torch.sigmoid(outputs["stop_tokens"]).data.max() <= 1.0
            assert torch.sigmoid(outputs["stop_tokens"]).data.min() >= 0.0
            optimizer.zero_grad()
            loss = criterion(outputs["decoder_outputs"], mel_spec, mel_lengths)
            stop_loss = criterion_st(outputs["stop_tokens"], stop_targets)
            loss = loss + criterion(outputs["model_outputs"], mel_postnet_spec, mel_lengths) + stop_loss
            loss.backward()
            optimizer.step()
        # check parameter changes
        count = 0
        for param, param_ref in zip(model.parameters(), model_ref.parameters()):
            # ignore pre-higway layer since it works conditional
            # if count not in [145, 59]:
            assert (param != param_ref).any(), "param {} with shape {} not updated!! \n{}\n{}".format(
                count, param.shape, param, param_ref
            )
            count += 1


class MultiSpeakeTacotronTrainTest(unittest.TestCase):
    @staticmethod
    def test_train_step():
        input_dummy = torch.randint(0, 24, (8, 128)).long().to(device)
        input_lengths = torch.randint(100, 128, (8,)).long().to(device)
        input_lengths = torch.sort(input_lengths, descending=True)[0]
        mel_spec = torch.rand(8, 30, c.audio["num_mels"]).to(device)
        mel_postnet_spec = torch.rand(8, 30, c.audio["num_mels"]).to(device)
        mel_lengths = torch.randint(20, 30, (8,)).long().to(device)
        mel_lengths[0] = 30
        stop_targets = torch.zeros(8, 30, 1).float().to(device)
        speaker_ids = torch.rand(8, 55).to(device)

        for idx in mel_lengths:
            stop_targets[:, int(idx.item()) :, 0] = 1.0

        stop_targets = stop_targets.view(input_dummy.shape[0], stop_targets.size(1) // c.r, -1)
        stop_targets = (stop_targets.sum(2) > 0.0).unsqueeze(2).float().squeeze()

        criterion = MSELossMasked(seq_len_norm=False).to(device)
        criterion_st = nn.BCEWithLogitsLoss().to(device)
        model = Tacotron2(num_chars=24, r=c.r, num_speakers=5, speaker_embedding_dim=55).to(device)
        model.train()
        model_ref = copy.deepcopy(model)
        count = 0
        for param, param_ref in zip(model.parameters(), model_ref.parameters()):
            assert (param - param_ref).sum() == 0, param
            count += 1
        optimizer = optim.Adam(model.parameters(), lr=c.lr)
        for i in range(5):
            outputs = model.forward(
                input_dummy, input_lengths, mel_spec, mel_lengths, cond_input={"x_vectors": speaker_ids}
            )
            assert torch.sigmoid(outputs["stop_tokens"]).data.max() <= 1.0
            assert torch.sigmoid(outputs["stop_tokens"]).data.min() >= 0.0
            optimizer.zero_grad()
            loss = criterion(outputs["decoder_outputs"], mel_spec, mel_lengths)
            stop_loss = criterion_st(outputs["stop_tokens"], stop_targets)
            loss = loss + criterion(outputs["model_outputs"], mel_postnet_spec, mel_lengths) + stop_loss
            loss.backward()
            optimizer.step()
        # check parameter changes
        count = 0
        for param, param_ref in zip(model.parameters(), model_ref.parameters()):
            # ignore pre-higway layer since it works conditional
            # if count not in [145, 59]:
            assert (param != param_ref).any(), "param {} with shape {} not updated!! \n{}\n{}".format(
                count, param.shape, param, param_ref
            )
            count += 1


class TacotronGSTTrainTest(unittest.TestCase):
    # pylint: disable=no-self-use
    def test_train_step(self):
        # with random gst mel style
        input_dummy = torch.randint(0, 24, (8, 128)).long().to(device)
        input_lengths = torch.randint(100, 128, (8,)).long().to(device)
        input_lengths = torch.sort(input_lengths, descending=True)[0]
        mel_spec = torch.rand(8, 30, c.audio["num_mels"]).to(device)
        mel_postnet_spec = torch.rand(8, 30, c.audio["num_mels"]).to(device)
        mel_lengths = torch.randint(20, 30, (8,)).long().to(device)
        mel_lengths[0] = 30
        stop_targets = torch.zeros(8, 30, 1).float().to(device)
        speaker_ids = torch.randint(0, 5, (8,)).long().to(device)

        for idx in mel_lengths:
            stop_targets[:, int(idx.item()) :, 0] = 1.0

        stop_targets = stop_targets.view(input_dummy.shape[0], stop_targets.size(1) // c.r, -1)
        stop_targets = (stop_targets.sum(2) > 0.0).unsqueeze(2).float().squeeze()

        criterion = MSELossMasked(seq_len_norm=False).to(device)
        criterion_st = nn.BCEWithLogitsLoss().to(device)
        model = Tacotron2(num_chars=24, r=c.r, num_speakers=5, use_gst=True, gst=c.gst).to(device)
        model.train()
        model_ref = copy.deepcopy(model)
        count = 0
        for param, param_ref in zip(model.parameters(), model_ref.parameters()):
            assert (param - param_ref).sum() == 0, param
            count += 1
        optimizer = optim.Adam(model.parameters(), lr=c.lr)
        for i in range(10):
            outputs = model.forward(
                input_dummy, input_lengths, mel_spec, mel_lengths, cond_input={"speaker_ids": speaker_ids}
            )
            assert torch.sigmoid(outputs["stop_tokens"]).data.max() <= 1.0
            assert torch.sigmoid(outputs["stop_tokens"]).data.min() >= 0.0
            optimizer.zero_grad()
            loss = criterion(outputs["decoder_outputs"], mel_spec, mel_lengths)
            stop_loss = criterion_st(outputs["stop_tokens"], stop_targets)
            loss = loss + criterion(outputs["model_outputs"], mel_postnet_spec, mel_lengths) + stop_loss
            loss.backward()
            optimizer.step()
        # check parameter changes
        count = 0
        for name_param, param_ref in zip(model.named_parameters(), model_ref.parameters()):
            # ignore pre-higway layer since it works conditional
            # if count not in [145, 59]:
            name, param = name_param
            if name == "gst_layer.encoder.recurrence.weight_hh_l0":
                # print(param.grad)
                continue
            assert (param != param_ref).any(), "param {} {} with shape {} not updated!! \n{}\n{}".format(
                name, count, param.shape, param, param_ref
            )
            count += 1

        # with file gst style
        mel_spec = (
            torch.FloatTensor(ap.melspectrogram(ap.load_wav(WAV_FILE)))[:, :30].unsqueeze(0).transpose(1, 2).to(device)
        )
        mel_spec = mel_spec.repeat(8, 1, 1)
        input_dummy = torch.randint(0, 24, (8, 128)).long().to(device)
        input_lengths = torch.randint(100, 128, (8,)).long().to(device)
        input_lengths = torch.sort(input_lengths, descending=True)[0]
        mel_postnet_spec = torch.rand(8, 30, c.audio["num_mels"]).to(device)
        mel_lengths = torch.randint(20, 30, (8,)).long().to(device)
        mel_lengths[0] = 30
        stop_targets = torch.zeros(8, 30, 1).float().to(device)
        speaker_ids = torch.randint(0, 5, (8,)).long().to(device)

        for idx in mel_lengths:
            stop_targets[:, int(idx.item()) :, 0] = 1.0

        stop_targets = stop_targets.view(input_dummy.shape[0], stop_targets.size(1) // c.r, -1)
        stop_targets = (stop_targets.sum(2) > 0.0).unsqueeze(2).float().squeeze()

        criterion = MSELossMasked(seq_len_norm=False).to(device)
        criterion_st = nn.BCEWithLogitsLoss().to(device)
        model = Tacotron2(num_chars=24, r=c.r, num_speakers=5, use_gst=True, gst=c.gst).to(device)
        model.train()
        model_ref = copy.deepcopy(model)
        count = 0
        for param, param_ref in zip(model.parameters(), model_ref.parameters()):
            assert (param - param_ref).sum() == 0, param
            count += 1
        optimizer = optim.Adam(model.parameters(), lr=c.lr)
        for i in range(10):
            outputs = model.forward(
                input_dummy, input_lengths, mel_spec, mel_lengths, cond_input={"speaker_ids": speaker_ids}
            )
            assert torch.sigmoid(outputs["stop_tokens"]).data.max() <= 1.0
            assert torch.sigmoid(outputs["stop_tokens"]).data.min() >= 0.0
            optimizer.zero_grad()
            loss = criterion(outputs["decoder_outputs"], mel_spec, mel_lengths)
            stop_loss = criterion_st(outputs["stop_tokens"], stop_targets)
            loss = loss + criterion(outputs["model_outputs"], mel_postnet_spec, mel_lengths) + stop_loss
            loss.backward()
            optimizer.step()
        # check parameter changes
        count = 0
        for name_param, param_ref in zip(model.named_parameters(), model_ref.parameters()):
            # ignore pre-higway layer since it works conditional
            # if count not in [145, 59]:
            name, param = name_param
            if name == "gst_layer.encoder.recurrence.weight_hh_l0":
                # print(param.grad)
                continue
            assert (param != param_ref).any(), "param {} {} with shape {} not updated!! \n{}\n{}".format(
                name, count, param.shape, param, param_ref
            )
            count += 1


class SCGSTMultiSpeakeTacotronTrainTest(unittest.TestCase):
    @staticmethod
    def test_train_step():
        input_dummy = torch.randint(0, 24, (8, 128)).long().to(device)
        input_lengths = torch.randint(100, 128, (8,)).long().to(device)
        input_lengths = torch.sort(input_lengths, descending=True)[0]
        mel_spec = torch.rand(8, 30, c.audio["num_mels"]).to(device)
        mel_postnet_spec = torch.rand(8, 30, c.audio["num_mels"]).to(device)
        mel_lengths = torch.randint(20, 30, (8,)).long().to(device)
        mel_lengths[0] = 30
        stop_targets = torch.zeros(8, 30, 1).float().to(device)
        speaker_embeddings = torch.rand(8, 55).to(device)

        for idx in mel_lengths:
            stop_targets[:, int(idx.item()) :, 0] = 1.0

        stop_targets = stop_targets.view(input_dummy.shape[0], stop_targets.size(1) // c.r, -1)
        stop_targets = (stop_targets.sum(2) > 0.0).unsqueeze(2).float().squeeze()
        criterion = MSELossMasked(seq_len_norm=False).to(device)
        criterion_st = nn.BCEWithLogitsLoss().to(device)
        model = Tacotron2(num_chars=24, r=c.r, num_speakers=5, speaker_embedding_dim=55, use_gst=True, gst=c.gst).to(
            device
        )
        model.train()
        model_ref = copy.deepcopy(model)
        count = 0
        for param, param_ref in zip(model.parameters(), model_ref.parameters()):
            assert (param - param_ref).sum() == 0, param
            count += 1
        optimizer = optim.Adam(model.parameters(), lr=c.lr)
        for i in range(5):
            outputs = model.forward(
                input_dummy, input_lengths, mel_spec, mel_lengths, cond_input={"x_vectors": speaker_embeddings}
            )
            assert torch.sigmoid(outputs["stop_tokens"]).data.max() <= 1.0
            assert torch.sigmoid(outputs["stop_tokens"]).data.min() >= 0.0
            optimizer.zero_grad()
            loss = criterion(outputs["decoder_outputs"], mel_spec, mel_lengths)
            stop_loss = criterion_st(outputs["stop_tokens"], stop_targets)
            loss = loss + criterion(outputs["model_outputs"], mel_postnet_spec, mel_lengths) + stop_loss
            loss.backward()
            optimizer.step()
        # check parameter changes
        count = 0
        for name_param, param_ref in zip(model.named_parameters(), model_ref.parameters()):
            # ignore pre-higway layer since it works conditional
            # if count not in [145, 59]:
            name, param = name_param
            if name == "gst_layer.encoder.recurrence.weight_hh_l0":
                continue
            assert (param != param_ref).any(), "param {} with shape {} not updated!! \n{}\n{}".format(
                count, param.shape, param, param_ref
            )
            count += 1
