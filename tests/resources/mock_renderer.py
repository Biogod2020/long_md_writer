from pathlib import Path

class MockRenderer:
    """Simulates rendering Markdown to HTML and capturing a screenshot."""
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def render_to_image(self, markdown_content: str, section_id: str) -> Path:
        """
        In a real scenario, this would use Playwright.
        For the mock, we just create a dummy PNG file.
        """
        image_path = self.output_dir / f"{section_id}.png"
        image_path.write_bytes(b"dummy_png_content")
        return image_path
