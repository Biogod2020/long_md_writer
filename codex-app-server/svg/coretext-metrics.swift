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
    let resolved_font_name: String
    let missing_characters: [String]
}

func measure(_ run: TextRun) -> TextMetric {
    let preferredName = run.font_family?.split(separator: ",").first.map {
        String($0).trimmingCharacters(in: .whitespacesAndNewlines)
    } ?? "Helvetica"
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
    var missing: [String] = []
    for character in run.text {
        var units = Array(String(character).utf16)
        var glyphs = Array(repeating: CGGlyph(), count: units.count)
        let covered = CTFontGetGlyphsForCharacters(font, &units, &glyphs, units.count)
        if !covered || glyphs.contains(0) {
            let value = String(character)
            if !missing.contains(value) { missing.append(value) }
        }
    }
    return TextMetric(
        width: Double(width),
        ascent: Double(ascent),
        descent: Double(descent),
        resolved_font_name: CTFontCopyPostScriptName(font) as String,
        missing_characters: missing
    )
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
