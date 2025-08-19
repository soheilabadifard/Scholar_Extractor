import undetected_chromedriver as uc
import sys

chrome_path = '/usr/bin/google-chrome'
try:
    driver = uc.Chrome(version_main=139, browser_executable_path=chrome_path)
    driver.get('https://www.google.com')
    print('Chrome launched successfully!')
    print('Title:', driver.title)
    driver.quit()
except Exception as e:
    print('Error launching Chrome:', e)
    sys.stdout.flush()
