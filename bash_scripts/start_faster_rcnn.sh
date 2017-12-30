#!/bin/bash

python MainEntryFaster_RCNN.py \
    --task=train_faster_rcnn \
    --is_training=True \
    --max_iter=200000 \
    --batch_size=16 \
    --learning_rate=0.1 \
    --decay_step=1000 \
    --decay_rate=0.96 \
    --input_dir=/data/hzwangjian1/TFTemplate/voc_train_data.pkl \
    --save_model_dir=/home/recsys/hzwangjian1/learntf/faster_rcnn_model \
    --save_model_freq=10000 \
    --summary_dir=/home/recsys/hzwangjian1/learntf/faster_rcnn_summary \
    --summary_freq=100 \
    --print_info_freq=10 \
    --valid_freq=1000 \
    --init_scale=0.01 \
    --keep_prob=0.8 \
    --vgg16_path=/data/hzwangjian1/TFTemplate/vgg16_weights.npz
