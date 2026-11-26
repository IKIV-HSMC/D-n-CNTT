@echo off
chcp 65001 >nul
echo ==============================================================================
echo        TỰ ĐỘNG NẠP MODEL ĐÃ HUẤN LUYỆN VÀO OLLAMA (DOCMIND)
echo ==============================================================================

where ollama >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [LỖI] Không tìm thấy lệnh 'ollama'. Vui lòng cài đặt hoặc bật Ollama trước!
    pause
    exit /b 1
)

echo [1/3] Đang kiểm tra file GGUF...
if not exist "mindmap-model-gguf\*.gguf" (
    if not exist "*.gguf" (
        echo [CẢNH BÁO] Không tìm thấy file .gguf trong thư mục mindmap-model-gguf!
        echo Hãy giải nén file mindmap-model-v2.zip tải từ Kaggle vào đây.
        pause
        exit /b 1
    )
)

echo [2/3] Đang nạp model vào Ollama với tên: docmind-model...
ollama create docmind-model -f Modelfile

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==============================================================================
    echo [THÀNH CÔNG] Đã nạp thành công 'docmind-model' vào Ollama!
    echo Bây giờ bạn có thể:
    echo  1. Kiểm tra thử: python test_trained_model.py
    echo  2. Hoặc cấu hình trong backend .env: OLLAMA_MODEL=docmind-model
    echo ==============================================================================
) else (
    echo [LỖI] Quá trình nạp model thất bại!
)

pause
