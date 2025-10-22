from undetected_chromedriver import Chrome, ChromeOptions
from joblass.config import CHROME_PROFILE_DIR
import shutil
import os


def create_undetected_chrome_driver():
    options = ChromeOptions()
    options.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-extensions")
    driver = Chrome(options=options)
    driver.get("https://google.com")
    print(f"✅ Chrome launched with user data dir: {CHROME_PROFILE_DIR}")
    return driver

def cleanup_driver(driver):
    if driver:
        driver.quit()
        print("✅ Chrome driver closed successfully.")
        
def delete_chrome_profile():


    if os.path.exists(CHROME_PROFILE_DIR):
        shutil.rmtree(CHROME_PROFILE_DIR)
        print(f"✅ Deleted Chrome profile directory: {CHROME_PROFILE_DIR}")
    else:
        print(f"ℹ️ Chrome profile directory does not exist: {CHROME_PROFILE_DIR}")