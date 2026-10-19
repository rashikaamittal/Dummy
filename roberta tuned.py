%%capture
!pip install transformers
!pip install pytorch-lightning

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from google.colab import drive

drive.mount('/content/drive', force_remount=False)

train_path = '/content/drive/MyDrive/ucc/ucc_train.csv'
val_path = '/content/drive/MyDrive/ucc/ucc_val.csv'
train_data = pd.read_csv(train_path)

train_data['unhealthy'] = np.where(train_data['healthy'] == 1, 0, 1)
train_data['generalisation_all'] = np.where(
    (train_data['generalisation_unfair'] == 1) | (train_data['generalisation'] == 1), 1, 0)

attributes = ['antagonize', 'condescending','dismissive','generalisation',
              'hostile','sarcastic','healthy']

train_data.head(5)

#print(train_data['generalisation_all'].sum())
#print(train_data['generalisation'].sum())
#print(train_data['generalisation_unfair'].sum())

train_data[attributes].sum().plot.bar()

from torch.utils.data import Dataset

class UCC_Dataset(Dataset):

  def __init__(self, data_path, tokenizer, attributes, max_token_len: int = 128, sample = 5000):
    self.data_path = data_path
    self.tokenizer = tokenizer
    self.attributes = attributes
    self.max_token_len = max_token_len
    self.sample = sample
    self._prepare_data()


  def _prepare_data(self):
    data = pd.read_csv(self.data_path)
    data['unhealthy'] = np.where(data['healthy'] == 1, 0, 1)
    if self.sample is not None:
      unhealthy = data.loc[data[attributes].sum(axis=1) > 0]
      clean = data.loc[data[attributes].sum(axis=1) == 0]
      self.data = pd.concat([unhealthy, clean.sample(self.sample, random_state=7)])
    else:
      self.data = data

  def __len__(self):
    return len(self.data)

  def __getitem__(self, index):
    item = self.data.iloc[index]
    comment = str(item.comment)
    attributes = torch.FloatTensor(item[self.attributes])
    tokens = self.tokenizer(comment,
                                        add_special_tokens=True,
                                        return_tensors='pt',
                                        truncation=True,
                                        padding='max_length',
                                        max_length=self.max_token_len,
                                        return_attention_mask = True)
    return {'input_ids': tokens.input_ids.flatten(), 'attention_mask': tokens.attention_mask.flatten(), 'labels': attributes}

import torch
from transformers import AutoTokenizer
model_name = 'roberta-base'
tokenizer = AutoTokenizer.from_pretrained(model_name)
ucc_ds = UCC_Dataset(train_path, tokenizer, attributes=attributes, sample=None)
ucc_ds_val = UCC_Dataset(val_path, tokenizer, attributes=attributes, sample=None)

ucc_ds.__getitem__(0)['labels'].shape, ucc_ds.__getitem__(0)['input_ids'].shape, ucc_ds.__getitem__(0)['attention_mask'].shape
#ucc_ds.__getitem__(0)

import pytorch_lightning as pl
from torch.utils.data import DataLoader

class UCC_Data_Module(pl.LightningDataModule):

  def __init__(self, train_path, val_path, attributes, batch_size: int = 16, max_token_length: int = 128,  model_name='roberta-base'):
    super().__init__()
    self.train_path = train_path
    self.val_path = val_path
    self.attributes = attributes
    self.batch_size = batch_size
    self.max_token_length = max_token_length
    self.model_name = model_name
    self.tokenizer = AutoTokenizer.from_pretrained(model_name)

  def setup(self, stage = None):
    if stage in (None, "fit"):
      self.train_dataset = UCC_Dataset(self.train_path, attributes=self.attributes, tokenizer=self.tokenizer)
      self.val_dataset = UCC_Dataset(self.val_path, attributes=self.attributes, tokenizer=self.tokenizer, sample=None)
    if stage == 'predict':
      self.val_dataset = UCC_Dataset(self.val_path, attributes=self.attributes, tokenizer=self.tokenizer, sample=None)

  def train_dataloader(self):
    return DataLoader(self.train_dataset, batch_size = self.batch_size, num_workers=4, shuffle=True)

  def val_dataloader(self):
    return DataLoader(self.val_dataset, batch_size = self.batch_size, num_workers=4, shuffle=False)

  def predict_dataloader(self):
    return DataLoader(self.val_dataset, batch_size = self.batch_size, num_workers=4, shuffle=False)


ucc_data_module = UCC_Data_Module(train_path, val_path, attributes=attributes)

ucc_data_module.train_dataloader()