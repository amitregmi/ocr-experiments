import math
import torch


def meshgrid(x, y):
    a = torch.arange(0, x)
    b = torch.arange(0, y)
    xx = a.repeat(y).view(-1, 1)
    yy = b.view(-1, 1).repeat(1, x).view(-1, 1)
    return torch.cat([xx, yy], 1)


def xywh2xyxy(boxes):
    xy = boxes[:, :2]
    wh = boxes[:, 2:]
    return torch.cat([xy - wh / 2, xy + wh / 2], 1)


def xyxy2xywh(boxes):
    xymin = boxes[:, :2]
    xymax = boxes[:, 2:]
    return torch.cat([(xymin + xymax) / 2, xymax - xymin + 1], 1)


def box_iou(box1, box2):
    lt = torch.max(box1[:, None, :2], box2[:, :2])  # N, M, 2
    rb = torch.min(box1[:, None, 2:], box2[:, 2:])  # N, M, 2

    wh = (rb - lt + 1).clamp(min=0)
    inter = wh[:, :, 0] * wh[:, :, 1]  # N, M
    area1 = (box1[:, 2] - box1[:, 0] + 1) * (box1[:, 3] - box1[:, 1] + 1)
    area2 = (box2[:, 2] - box2[:, 0] + 1) * (box2[:, 3] - box2[:, 1] + 1)
    iou = inter / (area1[:, None] + area2 - inter)
    return iou


class DataEncoder():
    def __init__(self):
        self.anchor_areas = [32*32., 64*64., 128 *
                             128., 256*256., 512*512.]  # p3 -> p7
        self.aspect_ratios = [1/2., 1/1., 2/1.]
        self.scale_ratios = [1., pow(2, 1/3.), pow(2, 2/3.)]
        self.anchor_wh = self._get_anchor_wh()

    def _get_anchor_wh(self):
        anchor_wh = []
        for s in self.anchor_areas:
            for ar in self.aspect_ratios:
                h = math.sqrt(s / ar)
                w = ar * h
                for sr in self.scale_ratios:
                    anchor_h = h * sr
                    anchor_w = w * sr
                    anchor_wh.append([anchor_w, anchor_h])
        num_fms = len(self.anchor_areas)
        return torch.Tensor(anchor_wh).view(num_fms, -1, 2)

    def _get_anchor_boxes(self, input_size):
        num_fms = len(self.anchor_areas)
        fm_sizes = [(input_size / pow(2., i + 3)).ceil()
                    for i in range(num_fms)]

        boxes = []
        for i in range(num_fms):
            fm_size = fm_sizes[i]
            grid_size = input_size / fm_size
            fm_w, fm_h = int(fm_size[0]), int(fm_size[1])
            xy = meshgrid(fm_w, fm_h) + 0.5
            xy = (xy * grid_size).view(fm_h, fm_w, 1, 2).expand(fm_h,
                                                                fm_w, 9, 2)  # (fm_h, fm_w, #anchor, (x, y)
            wh = self.anchor_wh[i].view(1, 1, 9, 2).expand(fm_h, fm_w, 9, 2)
            box = torch.cat([xy, wh], 3)  # [x, y, w, h]
            boxes.append(box.view(-1, 4))
        return torch.cat(boxes, 0)

    def encode(self, boxes, input_size):
        input_size = torch.Tensor(input_size)
        anchor_boxes = self._get_anchor_boxes(input_size)

        ious = box_iou(xywh2xyxy(anchor_boxes), boxes)
        boxes = xyxy2xywh(boxes)

        max_ious, max_ids = ious.max(1)
        boxes = boxes[max_ids]

        loc_xy = (boxes[:, :2] - anchor_boxes[:, :2]) / anchor_boxes[:, 2:]
        loc_wh = torch.log(boxes[:, 2:] / anchor_boxes[:, 2:])
        loc_targets = torch.cat([loc_xy, loc_wh], 1)
        masks = torch.ones(max_ids.size())
        masks[max_ious < 0.5] = 0
        return loc_targets, masks