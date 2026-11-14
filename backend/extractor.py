import os
import json
import docx
from pptx import Presentation
from pypdf import PdfReader

def clean_text(text):
    if not text:
        return ""
    return " ".join(text.strip().split())

def extract_pdf_to_structure(file_path):
    reader = PdfReader(file_path)
    nodes = []
    flashcards = []
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        lines = [clean_text(line) for line in text.split('\n') if clean_text(line)]
        if not lines:
            continue
        
        title = lines[0] if len(lines[0]) < 100 else f"Trang {i+1}"
        content = lines[1:] if len(lines[0]) < 100 else lines
        
        nodes.append({
            "topic": title,
            "subtopics": content[:10]
        })
        
        for line in lines:
            for separator in [" là ", " - ", ": "]:
                if separator in line and 10 < len(line) < 200:
                    parts = line.split(separator, 1)
                    flashcards.append({
                        "question": parts[0].strip(),
                        "answer": parts[1].strip()
                    })
                    break
                    
    return {
        "title": os.path.basename(file_path),
        "mindmap_structure": nodes,
        "flashcards": flashcards[:20]
    }

def extract_docx_to_structure(file_path):
    doc = docx.Document(file_path)
    nodes = []
    flashcards = []
    current_node = None
    
    for p in doc.paragraphs:
        text = clean_text(p.text)
        if not text:
            continue
            
        if p.style.name.startswith('Heading'):
            if current_node:
                nodes.append(current_node)
            current_node = {
                "topic": text,
                "subtopics": []
            }
        else:
            if current_node:
                if len(text) < 150:
                    current_node["subtopics"].append(text)
            else:
                current_node = {
                    "topic": "Chung",
                    "subtopics": [text]
                }
                
            for sep in [" là ", " - ", ": "]:
                if sep in text and 15 < len(text) < 150:
                    parts = text.split(sep, 1)
                    flashcards.append({
                        "question": parts[0].strip(),
                        "answer": parts[1].strip()
                    })
                    break

    if current_node:
        nodes.append(current_node)
        
    return {
        "title": os.path.basename(file_path),
        "mindmap_structure": nodes,
        "flashcards": flashcards[:20]
    }

def extract_pptx_to_structure(file_path):
    prs = Presentation(file_path)
    nodes = []
    flashcards = []
    
    for i, slide in enumerate(prs.slides):
        slide_title = f"Slide {i+1}"
        slide_contents = []
        
        if slide.shapes.title:
            slide_title = clean_text(slide.shapes.title.text)
            
        for shape in slide.shapes:
            if shape.has_text_frame and shape != slide.shapes.title:
                for paragraph in shape.text_frame.paragraphs:
                    txt = clean_text(paragraph.text)
                    if txt and txt != slide_title:
                        slide_contents.append(txt)
                        
                        for sep in [" là ", " - ", ": "]:
                            if sep in txt and 10 < len(txt) < 150:
                                parts = txt.split(sep, 1)
                                flashcards.append({
                                    "question": parts[0].strip(),
                                    "answer": parts[1].strip()
                                })
                                break
                                
        nodes.append({
            "topic": slide_title,
            "subtopics": slide_contents
        })
        
    return {
        "title": os.path.basename(file_path),
        "mindmap_structure": nodes,
        "flashcards": flashcards[:20]
    }

def local_extractor_to_json(file_path):
    ext = file_path.split('.')[-1].lower()
    if ext == 'pdf':
        data = extract_pdf_to_structure(file_path)
    elif ext == 'docx':
        data = extract_docx_to_structure(file_path)
    elif ext == 'pptx':
        data = extract_pptx_to_structure(file_path)
    else:
        raise ValueError("Định dạng không hỗ trợ!")
        
    output_filename = f"{os.path.splitext(file_path)[0]}_parsed.json"
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Trích xuất hoàn tất! File đã lưu: {output_filename}")
    return data

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Cách dùng: python extractor.py <duong_dan_file_tai_lieu>")
    else:
        local_extractor_to_json(sys.argv[1])
