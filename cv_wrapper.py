from typing import Dict, Tuple
import re
from glob import glob
import os.path
import logging
import subprocess
from PIL import Image
import cv2
import numpy as np
import colorlog
import pyocr

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(levelname)s:%(name)s:%(message)s'))
logger = colorlog.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class CVWrapperError(Exception):
    pass


class CVWrapper:
    current_ss: np.ndarray
    templates: Dict[str, np.ndarray]

    def __init__(self):
        self.templates = {}
        for img in glob("./imgs/*"):
            basename: str = os.path.splitext(
                os.path.basename(img)
            )[0]
            self.templates[basename] = cv2.imread(img, 0)
            logger.info(f"img loaded: {img}")
        tools = pyocr.get_available_tools()
        if not tools:
            logger.error("tesseract not found !")
            raise CVWrapperError
        self.tool = tools[0]

    def __get_ss(self):
        subprocess.run([
            "adb exec-out screencap -p > ss.png"
        ], shell=True)
        self.current_ss = cv2.imread('ss.png', 0)

    def get_remaining_sec(self, xmin: int, xmax: int, ymin: int, ymax: int, ss=True) -> int:
        if ss:
            self.__get_ss()
        cv2img = cv2.bitwise_not(cv2.threshold(
            self.current_ss[ymin:ymax, xmin:xmax],
            120,  # threshold
            255,
            cv2.THRESH_BINARY
        )[1])
        string = self.tool.image_to_string(
            Image.fromarray(cv2img),
            lang="eng",
            builder=pyocr.builders.TextBuilder(tesseract_layout=6)
        )
        try:
            time = re.findall(r'\d\d:\d\d', string)[0]
            logger.info(f"remaining time: {time}")
            remaining_min = int(time[:2])
            remaining_sec = int(time[3:])
            return remaining_min*60 + remaining_sec
        except IndexError:
            print(string)
            cv2.imwrite("test.png", cv2img)
            raise CVWrapperError("time could not be determined")

    def template_match(self,
                       template_name: str,
                       ss=True,
                       threshold=0.7) -> Tuple[int, int]:
        if ss:
            self.__get_ss()
        template = self.templates[template_name]

        res = cv2.matchTemplate(
            self.current_ss,
            template,
            cv2.TM_CCOEFF_NORMED
        )
        logger.info(f"template match for {template_name}: {res.max():.2f}")
        if res.max() < threshold:
            raise CVWrapperError(f"not found: {template_name}")

        loc = np.where(res == res.max())
        w, h = template.shape[::-1]

        return int(loc[1][0]+w/2), int(loc[0][0]+h/2)

    def template_match_any(self,
                           template_name: str,
                           threshold=0.7) -> Tuple[int, int]:
        self.__get_ss()

        for tname, template in self.templates.items():
            if template_name not in tname:
                continue
            res = cv2.matchTemplate(
                self.current_ss,
                template,
                cv2.TM_CCOEFF_NORMED
            )
            logger.info(f"template any match for {template_name}/{tname}: {res.max():.2f}")
            if res.max() < threshold:
                continue

            loc = np.where(res == res.max())
            w, h = template.shape[::-1]

            return int(loc[1][0]+w/2), int(loc[0][0]+h/2)
        raise CVWrapperError(f"not found: {template_name}")


if __name__ == "__main__":
    c = CVWrapper()
    c.get_remaining_sec(224, 270, 169, 191)
