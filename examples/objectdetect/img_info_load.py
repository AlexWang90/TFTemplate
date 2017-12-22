"""
Created by Alex Wang on 2017-12-09
"""

import os
import pickle
import xml.etree.ElementTree as ET
from multiprocessing import Pool

import numpy as np
from PIL import Image
from class_info import voc_classes_num, voc_class_to_ind
from scipy.sparse import csr_matrix

import generate_anchors

anchors = generate_anchors.generate_anchors()
anchors_ares = generate_anchors.cal_anchors_areas(anchors)
print(anchors)
print(anchors_ares)

def load_image_annotations(annotations_root_path, image_root_path, image_list, pickle_save_path):
    """
    load roi info from pickle file or xml files
    :param annotations_root_path:
    :param image_root_path:
    :param image_list:
    :param pickle_save_path:
    :return:
    """
    annotations_list = []
    if os.path.exists(pickle_save_path):
        print('load roi info from pickle file')
        annotations_list = pickle.load(open(pickle_save_path, 'rb'))
        return annotations_list

    print('load roi info from xml files.')
    for image_name in image_list:
        xml_path = os.path.join(annotations_root_path, image_name + '.xml')
        xml_feature = load_pascal_annotation(xml_path, image_name + '.jpg')
        image_path = os.path.join(image_root_path, image_name + '.jpg')
        img_feature = get_image_feature(image_path)
        xml_feature.update(img_feature)
        annotations_list.append(xml_feature)

    print('save roi info in pickle file.')
    pickle.dump(annotations_list, open(pickle_save_path, 'wb'))
    return annotations_list


def get_image_list(file_path):
    """
    get image list
    :param file_path: e.g.: E:\data\VOCdevkit\VOC2007\ImageSets\Main\trainval.txt
    :return:
    """
    image_list = []
    with open(file_path, 'r') as reader:
        line = reader.readline()
        while line:
            image_list.append(line.strip())
            line = reader.readline()

    return image_list


def get_image_feature(image_path):
    """
    get image width, height
    :param image_path:
    :return:
    """
    img = Image.open(image_path)
    (width, height) = img.size
    return {'image_width': width, 'image_height': height, 'image_path': image_path}


def load_pascal_annotation(filename, image_name):
    """
    Load image and bounding boxes info from XML file in the PASCAL VOC
    format.
    :param filename: xml annotation file path
    :return:
    """
    # filename = os.path.join(data_path, 'Annotations', index + '.xml')
    tree = ET.parse(filename)
    objs = tree.findall('object')

    # Exclude the samples labeled as difficult
    # non_diff_objs = [obj for obj in objs if int(obj.find('difficult').text) == 0]
    # if len(non_diff_objs) != len(objs):
    #     print ('Removed {} difficult objects from {}'.format(len(objs) - len(non_diff_objs), os.path.basename(filename)))
    # objs = non_diff_objs
    num_objs = len(objs)

    boxes = np.zeros((num_objs, 4), dtype=np.uint16)
    gt_classes = np.zeros((num_objs), dtype=np.int32)
    overlaps = np.zeros((num_objs, voc_classes_num), dtype=np.float32)
    # "Seg" area for pascal is just the box area
    seg_areas = np.zeros((num_objs), dtype=np.float32)
    ishards = np.zeros((num_objs), dtype=np.int32)

    # Load object bounding boxes into a data frame.
    for ix, obj in enumerate(objs):
        bbox = obj.find('bndbox')
        # Make pixel indexes 0-based
        x1 = float(bbox.find('xmin').text) - 1
        y1 = float(bbox.find('ymin').text) - 1
        x2 = float(bbox.find('xmax').text) - 1
        y2 = float(bbox.find('ymax').text) - 1

        diffc = obj.find('difficult')
        difficult = 0 if diffc == None else int(diffc.text)
        ishards[ix] = difficult

        cls = voc_class_to_ind[obj.find('name').text.lower().strip()]
        boxes[ix, :] = [x1, y1, x2, y2]
        gt_classes[ix] = cls
        overlaps[ix, cls] = 1.0
        seg_areas[ix] = (x2 - x1 + 1) * (y2 - y1 + 1)

    overlaps = csr_matrix(overlaps)

    # overlaps_arr = overlaps.toarray()
    # print(overlaps_arr.max(axis=1))
    # print(overlaps_arr.argmax(axis=1))

    return {'boxes': boxes,
            'gt_classes': gt_classes,
            'gt_ishard': ishards,
            'gt_overlaps': overlaps,
            'flipped': False,
            'seg_areas': seg_areas,
            'xml_path': filename,
            'image_name': image_name}


def generate_train_pathes(roi_info_list, thread_num = 4):
    """
    生成训练数据，每张图片随机选取256个anchors，正anchor和负anchors的占比接近于1:1，如果图像中少于128个正anchors，就用负样本来填充。
    考察训练集中的每张图像：
    a. 对每个标定的真值候选区域，与其重叠比例最大的anchor记为前景样本
    b. 对a)剩余的anchor，如果其与某个标定重叠比例大于0.7，记为前景样本；如果其与任意一个标定的重叠比例都小于0.3，记为背景样本
    c. 对a),b)剩余的anchor，弃去不用。
    d. 跨越图像边界的anchor弃去不用
    :param roi_info_list:
    :return:
    """
    pool = Pool(thread_num)
    train_info = pool.map(process_one_image_roi, roi_info_list)
    pool.close()
    pool.join()
    return train_info


def image_to_feature_map(length, pool_layer_num):
    """
    计算经过k层pool layer之后图片长度的变化
    :param length: width or height of image
    :param pool_layer_num: pool layer 层数，e.g.4
    :return:
    """
    for i in range(pool_layer_num):
        length = np.ceil(length / 2)
    return length


def process_one_image_roi(annotation_feature, pool_layer=4):
    """
    在一张图片中随机选取ROI区域
    :param annotation_feature:
    :param pool_layer: VGG16中输入图像和feature map的比例为16:1， 4次pool
    {'image_width':width, 'image_height':height,
            'image_path':image_path
            'boxes': boxes,             array([[262, 210, 323, 338],[164, 263, 252, 371],[4, 243,  66, 373],[240, 193, 294, 298],[276, 185, 311, 219]], dtype=uint16)
                                        [left, top, right, bottom]
            'gt_classes': gt_classes,   array([9, 9, 9, 9, 9])}
            'gt_ishard': ishards,       'gt_ishard': array([0, 0, 1, 0, 1])
            'gt_overlaps': overlaps,   <kx21 sparse matrix of type '<class 'numpy.float32'>'
            'flipped': False,
            'seg_areas': seg_areas,    array([ 7998.,  9701.,  8253.,  5830.,  1260.], dtype=float32)
            'xml_path':filename,
            'image_name': image_name}
    :return:
    """
    # 随机生成
    print('generate train data...')
    # TODO:
    pool_layer_num = 4
    base_size = 16
    W = image_to_feature_map(annotation_feature['image_width'], pool_layer_num)
    H = image_to_feature_map(annotation_feature['image_height'], pool_layer_num)

    for w in range(W):
        for h in range(H):
            delt_x = base_size * w
            delt_y = base_size * h



def run_generate_windows():
    """
    本地机器上生成训练语料
    :return:
    """
    info = load_pascal_annotation('E://data/VOCdevkit/VOC2007/Annotations/004696.xml', '004696.jpg')
    print(info)

    image_list = get_image_list('E://data/VOCdevkit/VOC2007/ImageSets/Main/trainval.txt')
    print('len of image_list:{}'.format(len(image_list)))
    print(image_list[0:10])

    roi_info = load_image_annotations('E://data/VOCdevkit/VOC2007/Annotations/',
                                      'E://data/VOCdevkit/VOC2007/JPEGImages', image_list, 'E://data/voc_roi_info.pkl')
    print('len of roi_info:{}'.format(len(roi_info)))
    print(roi_info[0:5])
    print('---------------------')
    print(roi_info[0])
    print(roi_info[1])


if __name__ == '__main__':
    print('img_info_load starts running...')
    run_generate_windows()


    # print(image_to_feature_map(252, 4))  # should be 16
