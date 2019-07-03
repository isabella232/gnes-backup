import ctypes
import random

from ..base import BasePreprocessor
from ...proto import gnes_pb2

import numpy as np
from PIL import Image
import zipfile
import os


class ImagePreprocessor(BasePreprocessor):
    def __init__(self, start_doc_id: int = 0,
                 random_doc_id: bool = True,
                 target_img_size: int = 224,
                 use_split: bool = True,
                 split_method: str = 'stride',
                 is_rgb: bool = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_doc_id = start_doc_id
        self.random_doc_id = random_doc_id
        self.target_img_size = target_img_size
        self.use_split = use_split
        self.split_method = split_method
        self.is_rgb = is_rgb

    def apply(self, doc: 'gnes_pb2.Document'):
        doc.doc_id = self.start_doc_id if not self.random_doc_id else random.randint(0, ctypes.c_uint(-1).value)
        doc.doc_type = gnes_pb2.Document.IMAGE
        if self.is_rgb:
            image_asarray = np.frombuffer(doc.raw_image.data, dtype=np.float32).reshape(doc.raw_image.shape[0],
                                                                        doc.raw_image.shape[1], 3)
        else:
            image_asarray = np.frombuffer(doc.raw_image.data, dtype=np.float32).reshape(doc.raw_image.shape[0],
                                                                                        doc.raw_image.shape[1], 1)

        raw_img = Image.fromarray(np.uint8(image_asarray))
        if self.use_split:
            image_set = self.split_image(raw_img)
            for ci, chunk in enumerate(image_set):
                c = doc.chunks.add()
                c.doc_id = doc.doc_id
                c.blob.CopyFrom(chunk)
                # c.offset_nd = ci
                c.weight = 1 / len(image_set)
        else:
            c = doc.chunks.add()
            c.doc_id = doc.doc_id
            c.blob.CopyFrom(doc.raw_image)
            # c.offset_nd = 0
            c.weight = 1.
        return doc

    def split_image(self, img: Image):
        if self.split_method == 'stride':
            return self.crop_imgs(img)
        elif self.split_method == 'segmentation':
            return self.seg_imgs(img)
        else:
            raise ValueError(
                'split_method: %s has not been implemented' % self.split_method)

    def crop_imgs(self, img: Image):
        chunk_list = []
        wide, height = img.size

        # area of cropped image
        crop_ratio = 2 / 3
        box_wide = crop_ratio * wide
        box_height = crop_ratio * height

        # stride for two directions
        # number of chunks after cropping: (wide_time + 1) * (height_time + 1)
        wide_time = 1
        height_time = 1

        stride_wide = (wide - box_wide) / wide_time
        stride_height = (height - box_height) / height_time

        # initialization
        left = 0
        right = box_wide
        top = 0
        bottom = box_height

        for i in range(height_time + 1):
            for j in range(wide_time + 1):
                area = (left, top, right, bottom)
                cropped_img = np.asarray(img.crop(area).resize((self.target_img_size, self.target_img_size)),
                                            dtype=np.float32)

                blob_cropped_img = gnes_pb2.NdArray()
                blob_cropped_img.data = cropped_img.tobytes()
                blob_cropped_img.shape.extend(cropped_img.shape)
                blob_cropped_img.dtype = cropped_img.dtype.name

                chunk_list.append(blob_cropped_img)
                left += stride_wide
                right += stride_wide
            left = 0
            right = box_wide
            top += stride_height
            bottom += stride_height
        return chunk_list

    def seg_imgs(self, img):
        pass

    def img_process_for_test(self, dirname: str):
        zipfile_ = zipfile.ZipFile(os.path.join(dirname, 'imgs/test.zip'), "r")
        test_img = []
        for img_file in zipfile_.namelist():
            image = Image.open(zipfile_.open(img_file, 'r')).resize((self.target_img_size, self.target_img_size))
            image_asarray = np.asarray(image, dtype=np.float32)
            blob = gnes_pb2.NdArray()
            blob.data = image_asarray.tobytes()
            blob.shape.extend(image_asarray.shape)
            blob.dtype = image_asarray.dtype.name
            test_img.append(blob)
        return test_img

