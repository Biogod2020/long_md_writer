import CoreText
import Foundation

struct TextRun: Decodable {
    let text: String
    let font_size: Double
    let font_family: String?
}

struct TextMetric: Encodable {
    let width: Double
    let ascent: Double
    let descent: Double
}

func measure(_ run: TextRun) -> TextMetric {
    let preferredName = run.font_family?.split(separator: ",").first.map(String.init) ?? "Helvetica"
    let font = CTFontCreateWithName(preferredName as CFString, CGFloat(run.font_size), nil)
    let attributes: [NSAttributedString.Key: Any] = [
        kCTFontAttributeName as NSAttributedString.Key: font,
    ]
    let attributed = NSAttributedString(string: run.text, attributes: attributes)
    let line = CTLineCreateWithAttributedString(attributed)
    var ascent: CGFloat = 0
    var descent: CGFloat = 0
    var leading: CGFloat = 0
    let width = CTLineGetTypographicBounds(line, &ascent, &descent, &leading)
    return TextMetric(width: Double(width), ascent: Double(ascent), descent: Double(descent))
}

do {
    let input = FileHandle.standardInput.readDataToEndOfFile()
    let runs = try JSONDecoder().decode([TextRun].self, from: input)
    let encoded = try JSONEncoder().encode(runs.map(measure))
    FileHandle.standardOutput.write(encoded)
} catch {
    FileHandle.standardError.write(Data("\\(error)\\n".utf8))
    exit(1)
}
