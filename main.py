import dataclasses
import logging

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
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36'
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


def _is_available_to_buy_argos(driver: WebDriver, item_name: str, url: str) -> Any:
    LOG.info(f"Loading {url} for item {item_name}")
    driver.get(url)
    #driver.save_screenshot(f'{item_name}.png')
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
    options.add_argument("--disable-extensions")
    options.add_argument("--proxy-server='direct://'")
    options.add_argument("--proxy-bypass-list=*")
    options.add_argument("--start-maximized")
    # options.add_argument("--headless") can't get this to work for now
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--lang=en-us")

    driver = webdriver.Chrome(options=options)
    return driver


def _run_shop(shop: Shop, driver: WebDriver):
    for item_name, url in shop.urls.items():
        last_record = db.find_latest_available(shop.name, item_name)
        previously_available = last_record and last_record.available
        is_available = False
        if shop.name.lower() == "argos":
            is_available = _is_available_to_buy_argos(driver, item_name, url)
            if is_available and not previously_available:
                LOG.info(f"Sending message as {item_name} is available in {shop.name} and not previously available")
                message.send_message(f"{item_name} is available now from {url}")
            else:
                LOG.info(f"Item {item_name} is not available in shop {shop.name} or was previously available")
        else:
            LOG.error(f"Shop {shop.name} is not configure")
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
    shops = _load_shops(config_filepath)
    driver = _create_chrome_web_driver()
    _run_shops(shops, driver)
    driver.quit()


if __name__ == "__main__":

    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    LOG.setLevel(logging.DEBUG)

    run()
