import torch
import torch.nn as nn
from torch.autograd import Variable


class RoIRotate(nn.Module):
    def __init__(self, height):
        super().__init__()
        self.height = height
        pass

    def forward(self, image, boxes):
        '''
        Args:
            image: tensor [#batch, Channel, H, W] or [Channel, H, W]
            boxes: tensor [#batch, #boxes, 5 (left, top, right, bottom, theta)] or [#boxes, 5]
        '''
        expand = False
        if len(image.size()) == 3:
            image.unsqueeze_(0)
            boxes.unsqueeze_(0)
            expand = True
        else:
            assert image.size(0) == boxes.size(0)

        batch_size = image.size(0)
        batch_result_boxes = []
        max_width = 0
        max_boxes = 0
        for img, bbs in zip(image, boxes):
            base_widths = bbs[..., 2] - bbs[..., 0]
            base_heights = bbs[..., 3] - bbs[..., 1]
            c_img, h_img, w_img = img.size()

            result_bbs = []
            for box, base_width, base_height in zip(bbs, base_widths, base_heights):
                aspect = base_width / base_height
                width = int(aspect * self.height)
                max_width = max(max_width, width)
                each_w = base_width / (width - 1)
                each_h = base_height / (self.height - 1)
                xx = Variable(torch.arange(0, width)) * each_w + box[0]
                xx = xx.view(1, -1).repeat(self.height, 1).view(self.height, width)
                yy = Variable(torch.arange(0, self.height)) * each_h + box[1]
                yy = yy.view(-1, 1).repeat(1, width).view(self.height, width)
                result = bilinear_interpolate_torch(img, xx, yy)
                result_bbs.append(result)

            max_boxes = max(max_boxes, len(result_bbs))
            batch_result_boxes.append(result_bbs)

        result = Variable(torch.zeros(batch_size, max_boxes, c_img, self.height, max_width))
        mask = torch.zeros(batch_size, max_boxes, max_width).byte()
        for i, boxes in enumerate(batch_result_boxes):
            for j, box in enumerate(boxes):
                _, _, w = box.size()
                mask[i, j, :w] = 1
                result[i, j, :, :, :w] = box

        if expand:
            result.squeeze_(0)
            mask.squeeze_(0)
        return result, mask


def bilinear_interpolate_torch(im, x, y):
    x0 = torch.floor(x).long()
    x1 = x0 + 1

    y0 = torch.floor(y).long()
    y1 = y0 + 1

    x0 = torch.clamp(x0, 0, im.shape[2]-1)
    x1 = torch.clamp(x1, 0, im.shape[2]-1)
    y0 = torch.clamp(y0, 0, im.shape[1]-1)
    y1 = torch.clamp(y1, 0, im.shape[1]-1)

    im_a = im[:, y0, x0]
    im_b = im[:, y1, x0]
    im_c = im[:, y0, x1]
    im_d = im[:, y1, x1]

    wa = (x1.float()-x) * (y1.float()-y)
    wb = (x1.float()-x) * (y-y0.float())
    wc = (x-x0.float()) * (y1.float()-y)
    wd = (x-x0.float()) * (y-y0.float())

    return im_a * wa + im_b * wb + im_c * wc + im_d * wd


def main():
    from PIL import Image
    import torchvision
    import torchvision.transforms as transforms
    img = Image.open("0.png")
    img = transforms.ToTensor()(img)
    img = torch.autograd.Variable(img)
    r = RoIRotate(100)

    bbs = torch.Tensor([[0, 0, 100, 200], [100.1, 0, 300, 200]])
    boxes, masks = r.forward(img, bbs)
    torchvision.utils.save_image(boxes.data, 'a.jpg')

    img = Image.open("0.png")
    img = transforms.ToTensor()(img)
    img = torch.autograd.Variable(img)
    r = RoIRotate(100)
    img = img.unsqueeze(0)
    bbs = torch.Tensor([[[0, 0, 100, 200], [100, 0, 300, 200]]])
    boxes, masks = r.forward(img, bbs)
    torchvision.utils.save_image(boxes.data[0], 'b.jpg')


main()
