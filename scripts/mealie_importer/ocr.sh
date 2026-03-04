#!/bin/bash

# ========================================
# convert inbox/*.pdf --> inbox/ocr_pdfs/ocr_*.pdf
# ========================================
# wsl
# sudo apt update
# sudo apt-get  install ocrmypdf python3-pip
# sudo apt-get install tesseract-ocr-deu
# sudo apt-get install tesseract-ocr-eng
# sudo apt-get install tesseract-lang
# ocrmypdf -v

cd inbox || exit
mkdir ocr_pdfs
for f in *.pdf; do
  [[ "$f" == ocr_* ]] && continue
  ocrmypdf --output-type pdf --force-ocr -l deu --deskew --rotate-pages --optimize 3 "$f" "ocr_pdfs/ocr_$f" || echo "FAIL: $f"
done
cd ..
