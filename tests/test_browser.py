from src.oalc_creator.helpers import get_browser

def test_browser():
    browser = get_browser()
    assert browser is not None
    page = browser.get('https://www.google.com')
    html = browser.page_source
    assert html is not None
    assert browser.title == 'Google'
    browser.quit()
