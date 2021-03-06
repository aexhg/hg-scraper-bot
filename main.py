import dataclasses
import logging
import os

import sys
from datetime import datetime as dt
from typing import Any, Dict, List

import yaml
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC

import click
import uuid
import message
import db

# logging.basicConfig(level=logging.DEBUG)
USER_AGENT = 'Mozilla/5.0 (X11; CrOS x86_64 14469.41.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.57 Safari/537.36'
LOG = logging.getLogger(__name__)


@dataclasses.dataclass
class Shop:

    name: str
    urls: Dict[str, str]

    @classmethod
    def from_yaml(cls, name: str, urls: Dict[str, str]) -> "Shop":
        return cls(name, urls)


@dataclasses.dataclass
class Shops:

    shops: List[Shop]

    @classmethod
    def from_yaml(cls, config: Dict[str, Any]) -> "Shops":
        shops = [Shop.from_yaml(shop_name, urls) for shop_name, urls in config.get("shops", {}).items()]

        return cls(shops)

def is_available_to_by_currys(driver: WebDriver, item_name: str, url: str) -> Any:
    LOG.info(f"Loading {url} for item {item_name}")
    driver.get(url)

    try:
        cookies_button = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "onetrust-accept-btn-handler"))
        )
        cookies_button.click()
    except TimeoutException:
        LOG.debug("No cookies button found for Currys")

    css_selector = "#js-product-detail > div:nth-child(1) > div.row.m-0.product-tile-name-wrapper-text > div.col-lg-4.col-xl-4.col-12.col-md-4.col-sm-4.attributes-section > div > div.prices-add-to-cart-actions > div.addToCartActionButton > div > div > button"

    try:
        buy_button = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )
        if buy_button.is_enabled():
            LOG.debug(f"{item_name} is available to buy from Currys")
            return True
        LOG.debug(f"{item_name} is not available to buy from Currys")
        return False
    except TimeoutException:
        LOG.info(f"The buy button was not found for Currys item {item_name}")


def _is_available_to_buy_argos(driver: WebDriver, item_name: str, url: str) -> Any:
    LOG.info(f"Loading {url} for item {item_name}")
    driver.get(url)
    # driver.save_screenshot(f'{item_name}.png')
    # check for accept cookies button
    try:
        accept_cookies_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "consent_prompt_submit"))
        )
        if accept_cookies_button:
            LOG.debug(f"Accepting cookies for Argos")
            accept_cookies_button.click()
    except TimeoutException:
        LOG.debug("No cookies button found")

    try:
        buy_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//button[@data-test='add-to-trolley-button-button']"))
        )

        if buy_button:
            LOG.info(f"{item_name} is available to buy from Argos")
            return True
    except TimeoutException:
        LOG.info(f"{item_name} unavailable")
    return False


def _create_chrome_web_driver():
    options = Options()
    # options.add_argument("headless")
    options.add_argument(f"user_agent={USER_AGENT}")
    options.add_argument("--window-size=1920,1080")
    # options.add_argument("--disable-extensions")
    # options.add_argument("--proxy-server='direct://'")
    # options.add_argument("--proxy-bypass-list=*")
    # options.add_argument("--start-maximized")
    # options.add_argument("--headless")# can't get this to work for now
    # options.add_argument("--disable-gpu")
    # options.add_argument("--disable-dev-shm-usage")
    # options.add_argument("--no-sandbox")
    # options.add_argument("--ignore-certificate-errors")
    options.add_argument("--lang=en-GB")
    options.add_argument('--disable-blink-features=AutomationControlled')
    driver = webdriver.Chrome(options=options)
    # Remove navigator.webdriver Flag using JavaScript
    #driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.implicitly_wait(5)
    return driver


def _run_shop(shop: Shop, driver: WebDriver):
    for item_name, url in shop.urls.items():
        last_record = db.find_latest_available(shop.name, item_name)
        previously_available = last_record and last_record.available
        is_available = False
        if shop.name.lower() == "argos":
            is_available = _is_available_to_buy_argos(driver, item_name, url)
        elif shop.name.lower() == "currys":
            is_available = is_available_to_by_currys(driver, item_name, url)
        else:
            LOG.error(f"Shop {shop.name} is not configured")
            continue

        if is_available and not previously_available:
            LOG.info(f"Sending message as {item_name} is available in {shop.name} and not previously available")
            message.send_message(f"{item_name} is available now from {url}")
        else:
            LOG.info(f"Item {item_name} is not available in shop {shop.name} or was previously available")
        db.upsert(db.ShopRecord(
            id=f"{shop.name}_{item_name}_{uuid.uuid4()}",
            shop=shop.name,
            item_name=item_name,
            url=url,
            available=is_available,
            time_stamp=dt.utcnow().isoformat()
        ))


def _run_shops(shops: Shops, driver: WebDriver):
    for shop in shops.shops:
        _run_shop(shop, driver)


def _load_shops(filepath: str) -> Shops:
    with open(filepath) as f:
        config = yaml.safe_load(f)
        return Shops.from_yaml(config)


@click.command()
@click.argument("config_filepath")
def run(config_filepath: str):
    driver = _create_chrome_web_driver()

    while True:
        if os.environ.get("SHUTDOWN"):
            break
        shops = _load_shops(config_filepath)
        _run_shops(shops, driver)

    driver.quit()


if __name__ == "__main__":

    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    LOG.setLevel(logging.DEBUG)

    run()
