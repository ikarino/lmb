'''
医療所建設の自動化
'''
from typing import Tuple
import subprocess
import time
import logging
import shutil
from tqdm import tqdm
import colorlog

from cv_wrapper import CVWrapper, CVWrapperError

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(levelname)s:%(name)s:%(message)s'))
logger = colorlog.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def adb_tap(x: int, y: int):
    subprocess.run([
        'adb', 'shell', 'input', 'touchscreen', 'tap',
        f'{x}', f'{y}'
    ])


def adb_swipe(x0: int, y0: int, x1: int, y1: int):
    subprocess.run([
        'adb', 'shell', 'input', 'swipe',
        f'{x0}', f'{y0}', f'{x1}', f'{y1}', '500'
    ])


class LordsMobileError(Exception):
    pass


class Infirmary:
    cv: CVWrapper
    infirmary_postion: Tuple[int, int]

    def __init__(self):
        if not shutil.which('adb'):
            logger.error('adb command not in PATH')
        proc = subprocess.run(['adb', 'devices'], stdout=subprocess.PIPE)
        if len(proc.stdout.decode("utf-8").split('\n')) < 4:
            logger.warning("no adb connected devices. trying to connect Nox.")
            subprocess.run("adb connect 127.0.0.1:62001", shell=True)
        self.cv = CVWrapper()

    def __check_infirmary_position(self):
        x, y = self.cv.template_match_any('infirmary')
        logger.info(f"infirmary position: (x, y)=({x},{y})")
        self.infirmary_position = (x, y)

    def __goto_territory_screen(self):
        # 1. すでに領地内であれば解決
        try:
            self.cv.template_match('button_tomap')
            return
        except CVWrapperError:
            pass

        # 2. マップ上であれば領地に戻る
        try:
            self.click_by_template_match('button_toterritory')
            time.sleep(2)  # 暗転で結構時間かかる
            return
        except CVWrapperError:
            pass

        # 3. 閉じるボタンが表示されている場合は閉じてみる
        try:
            self.click_by_template_match('button_close')
            time.sleep(1)
        except CVWrapperError:
            raise LordsMobileError('error in __goto territory')

        # 4. 閉じたあとに領地内であることを確認する
        try:
            self.cv.template_match('button_tomap')
        except CVWrapperError:
            raise LordsMobileError('error in __goto territory after close')

    def click(self, x, y, sec=1.0):
        adb_tap(x, y)
        time.sleep(sec)

    def click_by_template_match(self,
                                template_name: str,
                                threshold=0.7,
                                dx=0,
                                dy=0) -> None:
        '''
        templateに一致する(x, y)をクリックする

        Parameters
        ----------
        template_name: str
            テンプレートの名前
        dy: int, default 0
            x座標を少しずらす
        dx: int, default 0
            y座標を少しずらす
        '''
        x, y = self.cv.template_match(template_name, threshold=threshold)
        self.click(x+dx, y+dy)

    def run(self, rounds: int, wait_time=15):
        for round in range(rounds):
            print(f"round {round+1}===================")
            self.scrap()
            self.construct()
            for lv in range(6):
                print(f"lv {lv+1} -> {lv+2}")
                self.level_up()

            for lv in range(3):
                print(f"lv {lv+7} -> {lv+8}")
                self.level_up()
                self.help()
                self.get_mysteries_box()
                for i in tqdm(range(wait_time)):
                    time.sleep(1)
                self.auto_accelerate()
            time.sleep(3)

    def construct(self, sleep=5):
        self.click(*self.infirmary_position)  # 医療所
        self.click(510, 340)  # 医療所を選択
        self.click(610, 460)  # 建設ボタン
        while True:
            try:
                x, y = self.cv.template_match('gauge_building')
                break
            except CVWrapperError:
                continue
        self.click(x+220, y)  # 無料ボタン
        time.sleep(sleep)

    def level_up(self, sleep=1, ss=True):
        self.click(*self.infirmary_position)  # 医療所
        self.click(820, 480)  # レベルアップ
        self.click(610, 460)  # レベルアップボタン
        while True:
            try:
                x, y = self.cv.template_match('gauge_building', threshold=0.8, ss=ss)
                break
            except CVWrapperError:
                pass
        self.click(x+220, y)  # 無料ボタン
        time.sleep(sleep)

    def auto_accelerate(self, sleep=5, ss=True):
        x, y = self.cv.template_match('gauge_building', ss=ss)
        self.click(x+220, y)  # 加速ボタン
        self.click(740, 285)  # オート加速
        self.click(580, 470)  # 使用ボタン
        self.click(740, 165)  # 無料ボタン
        time.sleep(sleep)

    def get_remaining_sec(self) -> int:
        try:
            x, y = self.cv.template_match('gauge_building')
            sec = self.cv.get_remaining_sec(
                x+150, x+200,
                y-11, y+11,
                ss=False
            )
            return sec
        except CVWrapperError:
            return 999999

    def scrap(self, sleep=2):
        self.__check_infirmary_position()
        self.click(*self.infirmary_position)  # 医療所
        self.click(670, 490)  # 解体ボタン
        self.click(640, 200)  # 即解体ボタン
        self.click(555, 250)  # はいボタン
        time.sleep(sleep)

    def help(self, ss=True):
        if ss:
            self.__goto_territory_screen()
        try:
            x, y = self.cv.template_match('button_help', ss=ss)
        except CVWrapperError:
            logger.warning("help button not found")
            return
        self.click(x, y)
        self.click(480, 500)
        self.click(930, 35)

    def get_mysteries_box(self, ss=True):
        if ss:
            self.__goto_territory_screen()
        self.click(850, 400)
        self.click(480, 400)

    def level8loop(self, num: int, use5=False):
        if use5:
            maximum = 50
        else:
            maximum = 600

        for n in range(num):
            print(f"==== {n+1}/{num} round ====")
            self.scrap()
            self.construct()
            for lv in range(7):
                print(f"lv {lv+1} -> {lv+2}")
                self.level_up()
            self.get_mysteries_box(ss=False)

            for _ in range(int(maximum/2)):
                self.help(ss=False)
                time.sleep(2)
                sec = self.get_remaining_sec()
                if use5 and sec < 60*32:
                    self.auto_accelerate(ss=False)
                    break
                elif not use5 and sec < 60*27:
                    self.level_up(ss=False)
                    break

    def find_phantom_knight(self):
        def __move(direction: str):
            if direction == "right":
                adb_swipe(880, 270, 80, 270)
            elif direction == "left":
                adb_swipe(80, 270, 880, 270)
            elif direction == "up":
                adb_swipe(420, 100, 420, 440)
                adb_swipe(420, 100, 420, 440)
            elif direction == "down":
                adb_swipe(420, 440, 420, 100)
                adb_swipe(420, 440, 420, 100)
            time.sleep(1)

        __move('right')
        __move('up')
        counter = 2
        while True:
            for _ in range(counter):
                __move('left')
            for _ in range(counter):
                __move('down')
            counter += 1
            for _ in range(counter):
                __move('right')
            for _ in range(counter):
                __move('up')
            counter += 1

            if counter > 5:
                break


if __name__ == "__main__":
    inf = Infirmary()
    inf.level8loop(3, use5=True)
