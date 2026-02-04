from pathlib import Path
from playwright.async_api import async_playwright

class PlaywrightRenderer:
    """
    Renders HTML content to an image using Playwright (Async).
    """
    def __init__(self, output_dir: Path, headless: bool = True):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless

    async def render_to_image(self, markdown_content: str, section_id: str) -> Path:
        """
        Renders Markdown (converted to HTML) to a PNG screenshot.
        """
        # 1. Convert Markdown to HTML (Simple conversion for testing)
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: sans-serif; padding: 20px; }}
                img {{ max-width: 100%; border: 1px solid #ccc; }}
            </style>
        </head>
        <body>
            {self._markdown_to_html(markdown_content)}
        </body>
        </html>
        """
        
        temp_html_path = self.output_dir / f"{section_id}.html"
        temp_html_path.write_text(html_content, encoding="utf-8")
        
        output_image_path = self.output_dir / f"{section_id}.png"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            await page.goto(f"file://{temp_html_path.absolute()}")
            await page.screenshot(path=str(output_image_path), full_page=True)
            await browser.close()
            
        return output_image_path

    def _markdown_to_html(self, md: str) -> str:
        """Simple Markdown to HTML converter for testing."""
        # Replace image tags (already HTML in our workflow)
        # MarkdownQA inputs often contain raw HTML <img> tags
        return md.replace("\n", "<br>")
