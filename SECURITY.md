# Security

Security issue, API token, database connection string, бодит автомашины зураг,
улсын дугаарын мэдээллийг public issue эсвэл pull request-д бүү оруулна уу.

Repository-ийн GitHub **Security → Advisories → Report a vulnerability**
боломж идэвхтэй бол private report илгээнэ. Идэвхгүй бол credential, exploit
detail нийтлэхгүйгээр maintainer-аас private холбоо барих суваг хүснэ.

Credential ил болсон бол эхлээд тухайн үйлчилгээ дээр revoke/rotate хийж,
Vercel environment болон шаардлагатай device configuration-ийг шинэчилнэ.
Git-ээс файл устгах нь өмнөх commit history дахь secret-ийг арилгахгүй.

Backend service keys-ийг зөвхөн server environment-д хадгална. ESP32-д зөвхөн
төхөөрөмжийн upload token шаардлагатай. License plate болон зураг нь хувийн
мэдээлэл агуулж болох тул report-д зохиомол өгөгдөл ашиглана.
