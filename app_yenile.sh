#!/bin/bash
# projectiri.app'i yeniden imzalar — değişiklik sonrası imza bozulursa çalıştır
APP="/Users/iri/Desktop/projectiri.app"

echo "→ Eski imza siliniyor..."
codesign --remove-signature "$APP" 2>/dev/null

echo "→ Extended attribute'lar temizleniyor..."
xattr -cr "$APP"

echo "→ Yeniden imzalanıyor..."
codesign --force --deep -s - "$APP"

if codesign --verify "$APP" 2>/dev/null; then
    echo "✓ Hazır — app çift tıklamaya hazır"
else
    echo "✗ İmza yine bozuk, yardıma ihtiyacın var"
    exit 1
fi
