import logging
import os
import sys
from typing import Union

import requests
import selenium.webdriver.remote.webelement
from selenium.common import NoSuchElementException
from seleniumwire import webdriver
from seleniumwire.utils import decode
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from ffmpeg_progress_yield import FfmpegProgress


def check_exists_by_xpath(dr: webdriver.Chrome, xpath: str) -> Union[
    bool, selenium.webdriver.remote.webelement.WebElement]:
    try:
        el = dr.find_element(By.XPATH, xpath)
    except NoSuchElementException:
        return False
    return el


def finds_between(s: str, before: str, after: str) -> list:
    return [i.split(after)[0] for i in s.split(before)[1:] if after in i]


def find_between(s: str, first: str, last: str) -> str:
    try:
        start = s.index(first) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ''


if __name__ == '__main__':
    while True:
        url = input('Lütfen Dizikorea linki girin: ')

        if 'dizikorea' not in url:
            continue

        mobile_emulation = {
            'deviceMetrics': {'width': 360, 'height': 920, 'pixelRatio': 3.0},
            'userAgent': 'Mozilla/5.0 (Linux; Android 4.2.1; en-us; Nexus 5 Build/JOP40D) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19'}

        logging.getLogger('WDM').setLevel(logging.NOTSET)
        os.environ['WDM_LOG'] = 'false'
        options = Options()
        options.add_argument("--headless=chrome")
        options.add_experimental_option('mobileEmulation', mobile_emulation)
        options.add_extension('ublockorigin.crx')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)
        name = driver.title.split(' izle')[0]

        driver.execute_script("""
            var element = document.querySelector(".bey-video-reklam");
            if (element)
                element.parentNode.removeChild(element);
        """)

        source_text = ''
        download_url = ''
        req_headers = ''
        body = ''
        audio = {}
        types = {'256x144': 4, '640x360': 1, '426x240': 0, '852x480': 2, '1280x720': 3}
        bandwidths = {'256x144': 0, '640x360': 0, '426x240': 0, '852x480': 128000, '1280x720': 192000}
        error = False

        source = check_exists_by_xpath(driver, '//iframe[contains(@src,"/player/")]')
        vip = check_exists_by_xpath(driver, '//iframe[contains(@src,"//embed.php")]')
        vidmoly = check_exists_by_xpath(driver, '//iframe[contains(@src,"vidmoly")]')
        okru = check_exists_by_xpath(driver, '//iframe[contains(@src,"ok.ru")]')

        if source is not False:
            source_text = 'Ana'
            driver.switch_to.frame(source)
            element = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, '//div[contains(@class,"display") and @aria-label="Oynat"]')))
            driver.execute_script('arguments[0].click();', element)
            request = driver.wait_for_request('/master.txt?', timeout=30)
            req_headers = request.headers
            body = decode(request.response.body, request.response.headers.get('Content-Encoding', 'identity')).decode(
                'utf-8').splitlines()
        elif vip:
            source_text = 'Vip'
            driver.switch_to.frame(vip)
            element = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, '//div[contains(@class,"display") and @aria-label="Oynat"]')))
            driver.execute_script('arguments[0].click();', element)
            request = driver.wait_for_request('sibnet.ru', timeout=30)
            download_url = request.url
        elif vidmoly:
            source_text = 'Vidmoly'
            driver.switch_to.frame(vidmoly)
            element = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, '//div[contains(@class,"display") and @aria-label="Oynat"]')))
            driver.execute_script('arguments[0].click();', element)
            request = driver.wait_for_request('/master.m3u8', timeout=30)
            body = decode(request.response.body, request.response.headers.get('Content-Encoding', 'identity')).decode(
                'utf-8').splitlines()
        elif okru:
            source_text = 'OKRU'
            video_id = okru.get_attribute('src').split('videoembed/')[1]
            driver.get('https://m.ok.ru/video/' + video_id)
            element = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, '//a[contains(@href, "moviePlaybackRedirect")]')))
            video_url = element.get_attribute('href').replace('st.hls=off', 'st.hls=on')
            request = driver.wait_for_request('videoPreview', timeout=30)
            body = requests.get(video_url, headers=request.headers).text.splitlines()
        else:
            error = True

        driver.close()

        if error:
            print('Kaynak desteklenmiyor veya video yok!')
            continue

        print(name)
        print('Kaynak: ' + source_text)

        resolutions = []
        resolution = 0
        urls = []
        audios = []

        if not vip:
            print('--- Çözünürlükler ---')
            count = 0
            link = False
            for line in body:
                if 'RESOLUTION=' in line:
                    res = ''

                    if source or okru:
                        res = line.split('RESOLUTION=')[1]
                    elif vidmoly:
                        res = find_between(line, 'RESOLUTION=', ',')

                    resolutions.append(res)
                    print('[' + str(count) + ']: ' + res)
                    link = True
                elif link:
                    count += 1
                    urls.append(line)
                    link = False

            while True:
                resolution = input('Lütfen çözünürlük seçin: ')

                if resolution.isnumeric() and 0 <= int(resolution) <= (count - 1):
                    resolution = int(resolution)
                    break

            print('Seçilen: ' + resolutions[resolution])

        cmd = ''
        path = ''

        if os.path.exists(name + '.mp4'):
            os.remove(name + '.mp4')

        if source:
            if not os.path.exists('temp'):
                os.mkdir('temp')

            r = requests.get(urls[resolution], headers=req_headers)
            path = os.path.join('temp', name + '.m3u8')
            with open(path, 'w') as f:
                f.write(r.text)

            cmd = [
                'ffmpeg', '-protocol_whitelist', 'file,http,https,tcp,tls', '-allowed_extensions', 'ALL', '-i', path,
                '-bsf:a', 'aac_adtstoasc', '-c', 'copy', name + '.mp4'
            ]
        elif vip:
            cmd = [
                'ffmpeg', '-i', download_url, '-c', 'copy', name + '.mp4'
            ]
        elif vidmoly:
            cmd = [
                'ffmpeg', '-headers', 'referer: https://vidmoly.to/', '-i', urls[resolution], '-bsf:a',
                'aac_adtstoasc', '-c', 'copy', name + '.mp4'
            ]
        elif okru:
            cmd = [
                'ffmpeg', '-headers', 'referer: https://m.ok.ru/', '-i', urls[resolution], '-bsf:a',
                'aac_adtstoasc', '-c', 'copy', name + '.mp4'
            ]

        ff = FfmpegProgress(cmd)
        for progress in ff.run_command_with_progress():
            sys.stdout.write('\rİndiriliyor: ' + str(progress) + '/100')

        if source:
            if os.path.exists(path):
                os.remove(path)

        print('\nBaşarıyla indirildi!')
