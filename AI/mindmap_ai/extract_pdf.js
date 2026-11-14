const fs = require('fs');
const path = require('path');
const { PDFParse } = require('pdf-parse');

/**
 * Extract text and sections from a PDF file.
 * Returns { original_filename, extracted_text, sections }
 */
async function extractPdf(pdfPath) {
    const buf = fs.readFileSync(pdfPath);
    const parser = new PDFParse(new Uint8Array(buf));
    const res = await parser.getText();

    const fileName = path.basename(pdfPath);
    const sections = [];
    const allTextLines = [];

    let currentSection = null;

    for (let i = 0; i < res.pages.length; i++) {
        const page = res.pages[i];
        const rawText = (page.text || '').trim();
        if (!rawText) continue;

        // Split into non-empty lines
        const lines = rawText.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
        if (lines.length === 0) continue;

        // Filter out page footer markers like "-- 1 of 52 --"
        const contentLines = lines.filter(l => !/^--\s*\d+\s+of\s+\d+\s*--$/i.test(l));
        if (contentLines.length === 0) continue;

        allTextLines.push(...contentLines);

        // First line is candidate heading
        const firstLine = contentLines[0];
        const remaining = contentLines.slice(1).join('\n');

        // Check if page represents a major title or heading
        const isCover = (i === 0);
        const heading = isCover ? (firstLine.length < 100 ? firstLine : fileName.replace(/\.pdf$/i, '')) : firstLine;
        const level = isCover ? 1 : 2;

        if (contentLines.length === 1 && currentSection) {
            // Very short single-line page, append to current section
            currentSection.text += (currentSection.text ? '\n' : '') + firstLine;
        } else {
            currentSection = {
                heading: heading.substring(0, 100),
                level: level,
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

async function processAll() {
    const rawDir = path.resolve(__dirname, '../raw');
    const docsDir = path.resolve(__dirname, '../docs');

    if (!fs.existsSync(docsDir)) {
        fs.mkdirSync(docsDir, { recursive: true });
    }

    const files = fs.readdirSync(rawDir);
    const pdfFiles = files.filter(f => f.toLowerCase().endsWith('.pdf'));

    console.log(`Tìm thấy ${pdfFiles.length} file PDF trong raw/`);

    let count = 0;
    for (const f of pdfFiles) {
        const fullPath = path.join(rawDir, f);
        const outName = f.replace(/\.pdf$/i, '.json');
        const outPath = path.join(docsDir, outName);

        try {
            const data = await extractPdf(fullPath);
            fs.writeFileSync(outPath, JSON.stringify(data, null, 2), 'utf-8');
            console.log(`[${++count}/${pdfFiles.length}] ${data.sections.length} sections -> ${outName}`);
        } catch (err) {
            console.error(`Lỗi khi trích xuất ${f}:`, err.message);
        }
    }

    console.log(`Hoàn thành trích xuất ${count}/${pdfFiles.length} tài liệu vào docs/`);
}

processAll();
