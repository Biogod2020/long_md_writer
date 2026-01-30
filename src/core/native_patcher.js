/**
 * Native Patcher Bridge
 * Directly ported from Google's gemini-cli (edit.ts and textUtils.ts)
 */

function safeLiteralReplace(str, oldString, newString) {
  if (oldString === '' || !str.includes(oldString)) {
    return str;
  }
  if (!newString.includes('$')) {
    return str.split(oldString).join(newString);
  }
  const escapedNewString = newString.split('$').join('$$$$');
  return str.split(oldString).join(escapedNewString);
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
  const normalizedSearch = old_string.replace(/\r\n/g, '\n');
  const normalizedReplace = new_string.replace(/\r\n/g, '\n');

  const exactOccurrences = currentContent.split(normalizedSearch).length - 1;
  if (exactOccurrences === 1) {
    let modifiedCode = safeLiteralReplace(currentContent, normalizedSearch, normalizedReplace);
    modifiedCode = restoreTrailingNewline(currentContent, modifiedCode);
    return modifiedCode;
  }
  return null;
}

function calculateFlexibleReplacement(currentContent, old_string, new_string) {
  const normalizedSearch = old_string.replace(/\r\n/g, '\n');
  const normalizedReplace = new_string.replace(/\r\n/g, '\n');

  const sourceLines = currentContent.match(/.*(?:\n|$)/g)?.slice(0, -1) || [];
  const searchLinesStripped = normalizedSearch.split('\n').map(l => l.trim());
  const replaceLines = normalizedReplace.split('\n');

  let flexibleOccurrences = 0;
  let matchIdx = -1;
  
  for (let i = 0; i <= sourceLines.length - searchLinesStripped.length; i++) {
    const window = sourceLines.slice(i, i + searchLinesStripped.length);
    const windowStripped = window.map(l => l.trim());
    const isMatch = windowStripped.every((line, index) => line === searchLinesStripped[index]);

    if (isMatch) {
      flexibleOccurrences++;
      matchIdx = i;
    }
  }

  if (flexibleOccurrences === 1) {
    const firstLineInMatch = sourceLines[matchIdx];
    const indentation = firstLineInMatch.match(/^(\s*)/)[1] || '';
    const newBlockWithIndent = replaceLines.map(line => `${indentation}${line}`).join('\n');
    
    sourceLines.splice(matchIdx, searchLinesStripped.length, newBlockWithIndent + (newBlockWithIndent.endsWith('\n') ? '' : '\n'));
    let modifiedCode = sourceLines.join('');
    modifiedCode = restoreTrailingNewline(currentContent, modifiedCode);
    return modifiedCode;
  }
  return null;
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

  const pattern = tokens.map(t => t.replace(/[.*+?^${}()|[\\]/g, '\\$&')).join('\\s*');
  const flexibleRegex = new RegExp(`^(\s*)${pattern}`, 'm');

  const match = flexibleRegex.exec(currentContent);
  if (!match) return null;

  // Check for ambiguity
  const globalRegex = new RegExp(`^(\s*)${pattern}`, 'mg');
  const matches = currentContent.match(globalRegex);
  if (matches && matches.length > 1) return null;

  const indentation = match[1] || '';
  const newBlockWithIndent = normalizedReplace.split('\n').map(l => `${indentation}${l}`).join('\n');
  
  const modifiedCode = currentContent.replace(flexibleRegex, newBlockWithIndent);
  return restoreTrailingNewline(currentContent, modifiedCode);
}

// CLI Entry Point
const fs = require('fs');
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
