/**
 * Native Patcher Bridge (Scientific Alignment with gemini-cli)
 * 
 * Ported from: ref_repo/gemini-cli/packages/core/src/tools/edit.ts
 * and ref_repo/gemini-cli/packages/core/src/utils/textUtils.ts
 */

function safeLiteralReplace(str, oldString, newString) {
  if (oldString === '' || !str.includes(oldString)) {
    return str;
  }
  if (!newString.includes('$')) {
    return str.split(oldString).join(newString);
  }
  // The correct way to handle $ in JavaScript string replacement when using split/join
  // is actually just split/join! $ has no special meaning there.
  // The only place $ matters is in .replace(regex, string) or .replace(string, string)
  return str.split(oldString).join(newString);
}

function restoreTrailingNewline(originalContent, modifiedContent) {
  const hadTrailingNewline = originalContent.endsWith('\n');
  if (hadTrailingNewline && !modifiedContent.endsWith('\n')) {
    return modifiedContent + '\n';
  } else if (!hadTrailingNewline && modifiedContent.endsWith('\n')) {
    return modifiedContent.replace(/\n$/, '');
  }
  return modifiedContent;
}

function calculateExactReplacement(currentContent, old_string, new_string) {
  const normalizedCode = currentContent;
  const normalizedSearch = old_string.replace(/\r\n/g, '\n');
  const normalizedReplace = new_string.replace(/\r\n/g, '\n');

  const exactOccurrences = normalizedCode.split(normalizedSearch).length - 1;
  if (exactOccurrences > 0) {
    let modifiedCode = safeLiteralReplace(
      normalizedCode,
      normalizedSearch,
      normalizedReplace,
    );
    modifiedCode = restoreTrailingNewline(currentContent, modifiedCode);
    return modifiedCode;
  }
  return null;
}

function calculateFlexibleReplacement(currentContent, old_string, new_string) {
  const normalizedCode = currentContent;
  const normalizedSearch = old_string.replace(/\r\n/g, '\n');
  const normalizedReplace = new_string.replace(/\r\n/g, '\n');

  const sourceLines = normalizedCode.match(/.*(?:\n|$)/g)?.slice(0, -1) ?? [];
  const searchLinesStripped = normalizedSearch
    .split('\n')
    .map((line) => line.trim());
  const replaceLines = normalizedReplace.split('\n');

  let flexibleOccurrences = 0;
  let i = 0;
  while (i <= sourceLines.length - searchLinesStripped.length) {
    const window = sourceLines.slice(i, i + searchLinesStripped.length);
    const windowStripped = window.map((line) => line.trim());
    const isMatch = windowStripped.every(
      (line, index) => line === searchLinesStripped[index],
    );

    if (isMatch) {
      flexibleOccurrences++;
      const firstLineInMatch = window[0];
      const indentationMatch = firstLineInMatch.match(/^(\s*)/);
      const indentation = indentationMatch ? indentationMatch[1] : '';
      const newBlockWithIndent = replaceLines.map(
        (line) => `${indentation}${line}`,
      );
      sourceLines.splice(
        i,
        searchLinesStripped.length,
        newBlockWithIndent.join('\n') + (newBlockWithIndent.length > 0 ? '' : ''),
      );
      // Skip the newly inserted lines
      i += replaceLines.length;
    } else {
      i++;
    }
  }

  if (flexibleOccurrences > 0) {
    let modifiedCode = sourceLines.join('');
    // Fix join artifact: match() above keeps newlines, so we might need adjustment
    // Actually, join("") is correct if sourceLines already have \n
    modifiedCode = restoreTrailingNewline(currentContent, modifiedCode);
    return modifiedCode;
  }
  return null;
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function calculateRegexReplacement(currentContent, old_string, new_string) {
  const normalizedSearch = old_string.replace(/\r\n/g, '\n');
  const normalizedReplace = new_string.replace(/\r\n/g, '\n');

  const delimiters = ['(', ')', ':', '[', ']', '{', '}', '>', '<', '='];
  let processedString = normalizedSearch;
  for (const delim of delimiters) {
    processedString = processedString.split(delim).join(` ${delim} `);
  }

  const tokens = processedString.split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return null;

  const escapedTokens = tokens.map(escapeRegex);
  const pattern = escapedTokens.join('\\s*');
  const finalPattern = `^(\\s*)${pattern}`;
  const flexibleRegex = new RegExp(finalPattern, 'm');

  const match = flexibleRegex.exec(currentContent);
  if (!match) return null;

  const indentation = match[1] || '';
  const newLines = normalizedReplace.split('\n');
  const newBlockWithIndent = newLines
    .map((line) => `${indentation}${line}`)
    .join('\n');

  // CRITICAL: Escape $ in replacement string for .replace()
  const escapedReplace = newBlockWithIndent.replace(/\$/g, '$$$$');
  const modifiedCode = currentContent.replace(flexibleRegex, escapedReplace);

  return restoreTrailingNewline(currentContent, modifiedCode);
}

// CLI Entry Point
const fs = require('fs');
try {
  const input = JSON.parse(fs.readFileSync(0, 'utf-8'));
  const { content, search, replace } = input;

  let result = calculateExactReplacement(content, search, replace);
  if (result === null) result = calculateFlexibleReplacement(content, search, replace);
  if (result === null) result = calculateRegexReplacement(content, search, replace);

  if (result !== null) {
    process.stdout.write(JSON.stringify({ success: true, result }));
  } else {
    process.stdout.write(JSON.stringify({ success: false, error: 'No unique match found.' }));
  }
} catch (e) {
  process.stdout.write(JSON.stringify({ success: false, error: e.message }));
}
