# Contributing

## Ажил эхлэхийн өмнө

1. [README](README.md)-ийн дагуу local environment бэлтгэнэ.
2. `git status` болон branch-аа шалгана. Өмнөх uncommitted өөрчлөлтийг хадгална.
3. Ажлын хүрээнд `feat/…`, `fix/…`, `docs/…` гэх мэт ойлгомжтой branch үүсгэнэ.
4. Тухайн API, schema, firmware data flow-ийг уншаад жижиг өөрчлөлт хийнэ.

## Код ба шалгалт

- Одоогийн Python, Flask, Arduino convention-ийг дагана.
- Secrets-ийг `.env`, firmware-ийн `secrets.h` дотор хадгална; template-д бодит
  credential бичихгүй.
- API input validation, network timeout, error fallback-ийг хадгална.
- Schema өөрчлөхөд хуучин өгөгдөл, deployment-ийн нийцлийг тайлбарлана.
- Runtime dependencies-ийг бага байлгана; hosted inference-д native vision
  packages шаардлагагүй.

```powershell
python -m unittest discover -s tests -v
git diff --check
```

Live service эсвэл hardware шалгалт хийсэн эсэхийг тусад нь тэмдэглэнэ.
Шинэ Workflow contract авахдаа Roboflow MCP-ээр бодит definition, response-ийг
шалгаж, [capture setup](docs/CAPTURE_SETUP.md)-ийн зааврыг дагана.

## Pull request

PR нь асуудал, эцсийн ажиллагаа, шалгасан command болон үлдсэн хязгаарлалтыг
тайлбарласан байна. `fix: …`, `feat: …`, `docs: …`, `chore: …` зэрэг тодорхой
commit title ашиглана. Photo, plate data, token болон database URL оруулахгүй.
Dependency, firmware, API өөрчлөлттэй хамт холбогдох docs-ийг шинэчилнэ.
