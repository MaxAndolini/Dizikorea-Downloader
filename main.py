import logging
import os
import sys

import requests
from selenium.webdriver import DesiredCapabilities
from seleniumwire import webdriver
from seleniumwire.utils import decode
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from ffmpeg_progress_yield import FfmpegProgress

if __name__ == '__main__':
    while True:
        url = input('Lütfen Dizikorea linki girin: ')

        if 'dizikorea' not in url:
            continue

        mobile_emulation = {
            'deviceMetrics': {'width': 360, 'height': 840, 'pixelRatio': 3.0},
            'userAgent': 'Mozilla/5.0 (Linux; Android 4.2.1; en-us; Nexus 5 Build/JOP40D) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19'}

        logging.getLogger('WDM').setLevel(logging.NOTSET)
        os.environ['WDM_LOG'] = 'false'
        options = Options()
        options.headless = True
        options.add_experimental_option('mobileEmulation', mobile_emulation)
        caps = DesiredCapabilities().CHROME
        # caps['pageLoadStrategy'] = 'normal'  #  Waits for full page load
        caps['pageLoadStrategy'] = 'eager'  # Do not wait for full page load
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), desired_capabilities=caps,
                                  options=options)
        driver.get(url)
        name = driver.title.split(' izle')[0]

        driver.execute_script("""
            var element = document.querySelector(".bey-video-reklam");
            if (element)
                element.parentNode.removeChild(element);
        """)

        iframe = driver.find_element(By.XPATH, '//iframe[contains(@src,"/player/")]')
        driver.switch_to.frame(iframe)
        test = driver.find_element(By.XPATH, '//div[contains(@class,"display") and @aria-label="Oynat"]')
        driver.execute_script('arguments[0].click();', test)
        request = driver.wait_for_request('/master.txt?', timeout=30)
        body = decode(request.response.body, request.response.headers.get('Content-Encoding', 'identity'))
        driver.close()

        print(name)
        print('--- Çözünürlükler ---')
        resolutions = []
        urls = []
        count = 0
        link = False
        for line in body.decode('utf-8').splitlines():
            if 'RESOLUTION=' in line:
                res = line.split('RESOLUTION=')[1]
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

        if not os.path.exists('temp'):
            os.mkdir('temp')

        r = requests.get(urls[resolution], headers=request.headers)
        path = os.path.join('temp', name + '.m3u')
        with open(path, 'w') as f:
            f.write(r.text)

        if os.path.exists(name + '.mp4'):
            os.remove(name + '.mp4')

        cmd = [
            'ffmpeg', '-protocol_whitelist', 'file,http,https,tcp,tls', '-allowed_extensions', 'ALL', '-i', path,
            '-bsf:a', 'aac_adtstoasc', '-c', 'copy', name + '.mp4'
        ]

        ff = FfmpegProgress(cmd)
        for progress in ff.run_command_with_progress():
            sys.stdout.write('\rİndiriliyor: ' + str(progress) + '/100')

        if os.path.exists(path):
            os.remove(path)

        print('\nBaşarıyla indirildi!')
