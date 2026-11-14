const fs = require('fs');
const path = require('path');
const AdmZip = require('adm-zip');
const { PDFParse } = require('pdf-parse');
const WordExtractor = require('word-extractor');

const rawDir = path.resolve(__dirname, '../raw');
const docsDir = path.resolve(__dirname, '../docs');

if (!fs.existsSync(docsDir)) {
    fs.mkdirSync(docsDir, { recursive: true });
}

function sanitizeName(name) {
    return name
        .replace(/#/g, 'CSharp')
        .replace(/&/g, 'and')
        .replace(/\s+\./g, '.')
        .replace(/[?*:<>\/\\|"]/g, '')
        .trim();
}

// 1. Trích xuất PDF
async function extractPdf(filePath) {
    const buf = fs.readFileSync(filePath);
    const parser = new PDFParse(new Uint8Array(buf));
    const res = await parser.getText();
    const fileName = path.basename(filePath);

    const sections = [];
    const allTextLines = [];
    let currentSection = null;

    for (let i = 0; i < res.pages.length; i++) {
        const page = res.pages[i];
        const rawText = (page.text || '').trim();
        if (!rawText) continue;

        const lines = rawText.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
        const contentLines = lines.filter(l => !/^--\s*\d+\s+of\s+\d+\s*--$/i.test(l));
        if (contentLines.length === 0) continue;

        allTextLines.push(...contentLines);

        const firstLine = contentLines[0];
        const remaining = contentLines.slice(1).join('\n');
        const isCover = (i === 0);
        const heading = isCover ? (firstLine.length < 100 ? firstLine : fileName.replace(/\.pdf$/i, '')) : firstLine;

        if (contentLines.length === 1 && currentSection) {
            currentSection.text += (currentSection.text ? '\n' : '') + firstLine;
        } else {
            currentSection = {
                heading: heading.substring(0, 100),
                level: isCover ? 1 : 2,
                text: remaining
            };
            sections.push(currentSection);
        }
    }

    return {
        original_filename: fileName,
        extracted_text: allTextLines.join('\n'),
        sections: sections
    };
}

// 2. Trích xuất PPTX
function extractPptx(filePath) {
    const zip = new AdmZip(filePath);
    const entries = zip.getEntries();
    const fileName = path.basename(filePath);

    const slideEntries = entries
        .filter(e => /^ppt\/slides\/slide\d+\.xml$/i.test(e.entryName))
        .sort((a, b) => {
            const numA = parseInt(a.entryName.replace(/\D/g, ''), 10);
            const numB = parseInt(b.entryName.replace(/\D/g, ''), 10);
            return numA - numB;
        });

    const sections = [];
    const allTextLines = [];

    for (let i = 0; i < slideEntries.length; i++) {
        const xml = slideEntries[i].getData().toString('utf-8');
        // Trích xuất tất cả text bên trong <a:t>...</a:t>
        const matches = [...xml.matchAll(/<a:t[^>]*>(.*?)<\/a:t>/gs)];
        const textRuns = matches.map(m => m[1].replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').trim()).filter(Boolean);

        if (textRuns.length === 0) continue;

        allTextLines.push(...textRuns);

        const heading = textRuns[0];
        const remaining = textRuns.slice(1).join('\n');
        sections.push({
            heading: heading.substring(0, 100),
            level: (i === 0) ? 1 : 2,
            text: remaining
        });
    }

    return {
        original_filename: fileName,
        extracted_text: allTextLines.join('\n'),
        sections: sections
    };
}

// 3. Trích xuất DOCX
function extractDocx(filePath) {
    const zip = new AdmZip(filePath);
    const fileName = path.basename(filePath);
    const entry = zip.getEntry('word/document.xml');
    if (!entry) return null;

    const xml = entry.getData().toString('utf-8');
    const sections = [];
    const allTextLines = [];
    let cur = null;

    const pRegex = /<w:p(?:[\s>].*?<\/w:p>)/gs;
    let pMatch;

    while ((pMatch = pRegex.exec(xml)) !== null) {
        const pXml = pMatch[0];
        const tMatches = [...pXml.matchAll(/<w:t[^>]*>(.*?)<\/w:t>/gs)];
        const pText = tMatches.map(m => m[1].replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')).join('').trim();
        if (!pText) continue;

        allTextLines.push(pText);

        const styleMatch = pXml.match(/<w:pStyle\s+[^>]*w:val="([^"]+)"/i);
        const styleVal = styleMatch ? styleMatch[1] : '';

        const headingMatch = styleVal.match(/heading\s*(\d+)/i);
        if (headingMatch) {
            const lv = parseInt(headingMatch[1], 10);
            cur = {
                heading: pText,
                level: lv,
                text: ''
            };
            sections.push(cur);
        } else if (cur) {
            cur.text += (cur.text ? '\n' : '') + pText;
        }
    }

    return {
        original_filename: fileName,
        extracted_text: allTextLines.join('\n'),
        sections: sections
    };
}

// 4. Trích xuất DOC
async function extractDoc(filePath) {
    const fileName = path.basename(filePath);
    const extractor = new WordExtractor();
    const doc = await extractor.extract(filePath);
    const text = doc.getBody();

    const lines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
    const sections = [];
    let cur = null;

    for (const line of lines) {
        // Dự đoán heading nếu là dòng số thứ tự hoặc in hoa
        if (/^\d+(\.\d+)*\s+[A-Z]/.test(line) || (/^[A-Z\s]{4,50}$/.test(line) && line.length < 50)) {
            cur = {
                heading: line,
                level: 2,
                text: ''
            };
            sections.push(cur);
        } else if (cur) {
            cur.text += (cur.text ? '\n' : '') + line;
        }
    }

    return {
        original_filename: fileName,
        extracted_text: text,
        sections: sections
    };
}

async function main() {
    const files = fs.readdirSync(rawDir);
    console.log(`Tìm thấy tổng cộng ${files.length} file trong raw/`);

    let success = 0;
    for (const f of files) {
        const fullPath = path.join(rawDir, f);
        const ext = path.extname(f).toLowerCase();
        const baseName = sanitizeName(path.basename(f, ext));
        const outName = `${baseName}.json`;
        const outPath = path.join(docsDir, outName);

        let data = null;
        try {
            if (ext === '.pdf') {
                data = await extractPdf(fullPath);
            } else if (ext === '.pptx') {
                data = extractPptx(fullPath);
            } else if (ext === '.docx') {
                data = extractDocx(fullPath);
            } else if (ext === '.doc') {
                data = await extractDoc(fullPath);
            }

            if (data && data.extracted_text && data.extracted_text.length > 50) {
                fs.writeFileSync(outPath, JSON.stringify(data, null, 2), 'utf-8');
                success++;
                console.log(`[OK] ${f} -> ${outName} (${data.sections.length} sections, ${data.extracted_text.length} chars)`);
            }
        } catch (err) {
            console.error(`[SKIP] ${f}:`, err.message);
        }
    }

    console.log(`\n===> Hoàn thành xuất ${success} tài liệu chất lượng cao vào docs/!`);
}

main();
