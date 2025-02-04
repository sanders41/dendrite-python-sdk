from typing import Union, List, TYPE_CHECKING
from playwright.async_api import Page, FrameLocator, ElementHandle
from bs4 import BeautifulSoup
from loguru import logger

from dendrite_sdk._core.dendrite_element import DendriteElement

if TYPE_CHECKING:
    from dendrite_sdk._core.dendrite_page import DendritePage

from dendrite_sdk._core._js import (
    GENERATE_DENDRITE_IDS_IFRAME_SCRIPT,
)
from dendrite_sdk._dom.util.mild_strip import mild_strip_in_place


async def expand_iframes(
    page: Page,
    page_soup: BeautifulSoup,
    iframe_path: str = "",
    frame: Union[ElementHandle, None] = None,
):

    if frame is None:
        iframes = await page.query_selector_all("iframe")
    else:
        content_frame = await frame.content_frame()
        if not content_frame:
            return
        iframes = await content_frame.query_selector_all("iframe")
    for iframe in iframes:
        # TODO: kolla om iframe inte har doc eller body, skippa då
        iframe_id = await iframe.get_attribute("d-id")
        if iframe_id is None:
            continue

        new_iframe_path = ""
        if iframe_path:
            new_iframe_path = f"{iframe_path}|"
        new_iframe_path = f"{new_iframe_path}{iframe_id}"

        content_frame = await iframe.content_frame()
        if content_frame is None:
            continue

        await content_frame.evaluate(
            GENERATE_DENDRITE_IDS_IFRAME_SCRIPT, {"frame_path": new_iframe_path}
        )

        frame_content = await content_frame.content()

        frame_tree = BeautifulSoup(frame_content, "html.parser")
        mild_strip_in_place(frame_tree)
        merge_iframe_to_page(iframe_id, page_soup, frame_tree)
        await expand_iframes(
            page,
            page_soup,
            new_iframe_path,
            iframe,
        )


def merge_iframe_to_page(
    iframe_id: str,
    page: BeautifulSoup,
    iframe: BeautifulSoup,
):
    iframe_element = page.find("iframe", {"d-id": iframe_id})
    if iframe_element is None:
        logger.debug(f"Could not find iframe with ID {iframe_id} in page soup")
        return

    iframe_element.replace_with(iframe)


def get_frame_context(page: Page, iframe_path: str) -> Union[FrameLocator, Page]:
    iframe_path_list = iframe_path.split("|")
    frame_context = page
    for iframe_id in iframe_path_list:
        frame_context = frame_context.frame_locator(f"[tf623_id='{iframe_id}']")
    return frame_context


async def get_all_elements_from_selector(
    page: "DendritePage", selector: str
) -> List[DendriteElement]:
    dendrite_elements: List[DendriteElement] = []
    soup = await page._get_soup()
    elements = soup.select(selector)

    for element in elements:
        frame = page._get_context(element)
        d_id = element.get("d-id", "")
        locator = frame.locator(f"xpath=//*[@d-id='{d_id}']")

        if not d_id:
            continue

        if isinstance(d_id, list):
            d_id = d_id[0]

        dendrite_elements.append(
            DendriteElement(
                d_id,
                locator,
                page.dendrite_browser,
            )
        )

    if len(dendrite_elements) == 0:
        raise Exception(f"No elements found for selector '{selector}'")

    return dendrite_elements
