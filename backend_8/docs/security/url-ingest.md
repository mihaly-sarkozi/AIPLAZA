# URL Ingest Security

## Cel

A URL ingest kulso weboldalakrol tolt le tartalmat a knowledge pipeline szamara. Ez SSRF es adatkiaramlasi kockazat, ezert a web/API process csak ingest run-t es outbox jobot hoz letre; a letoltes worker oldalon tortenik.

## Fontos env varok

- `KNOWLEDGE_URL_INGEST_ENABLED`: productionben csak akkor legyen `true`, ha az izolalt worker es egress policy kesz.
- `KNOWLEDGE_URL_INGEST_WORKER_ISOLATED`: production guard ezt varja el URL ingest engedelyezes mellett.
- `KNOWLEDGE_URL_INGEST_MAX_REDIRECTS`: maximum redirect szam, jelenlegi policy legfeljebb 5-re korlatozza.
- `KNOWLEDGE_URL_INGEST_MAX_RESPONSE_BYTES`: letoltesi byte limit, streaming kozben is ellenorzott.
- `KNOWLEDGE_URL_INGEST_ALLOWED_CONTENT_TYPES`: engedelyezett content-type lista.

## Mit ved

- Csak `http` es `https` scheme engedelyezett.
- Userinfo tiltott (`http://user@host`), mert host-smuggling kockazat.
- Private, loopback, link-local, metadata, multicast, reserved es unspecified IP blokkolt.
- DNS rebinding ellen a request elott uj resolve tortenik.
- Minden redirect target ujravalidalt.
- `https -> http` downgrade tiltott.
- Redirect loop es tul sok redirect kulon hibakoddal megall.
- Content-Length es streaming response meret limitelt.
- Content-Type allowlist ellenorzott; hianyzo content-type eseten az elso chunk szovegszerusege ellenorzott.

## Gepi hibakodok

- `INVALID_SCHEME`
- `USERINFO_NOT_ALLOWED`
- `PRIVATE_IP_BLOCKED`
- `DNS_RESOLUTION_FAILED`
- `DNS_REBINDING_DETECTED`
- `REDIRECT_LIMIT_EXCEEDED`
- `REDIRECT_DOWNGRADE_BLOCKED`
- `CONTENT_TYPE_NOT_ALLOWED`
- `CONTENT_LENGTH_TOO_LARGE`
- `RESPONSE_TOO_LARGE`
- `DOWNLOAD_TIMEOUT`

API valaszban a kod a kozos error schema `code` mezojebe kerul. A logban lehet reszletesebb reason/host adat, de response-ba productionben ne keruljon belso reszlet.

## Production checklist

- URL ingest worker kulon process/kontener: `INSTANCE_ROLE=worker`.
- Egress policy: csak 80/443 outbound, internal/private tartomany tiltva.
- Redis es object storage production guardok zold allapotban.
- `/readyz` ellenorizze az URL ingest isolation guardot.
- URL ingest rejection metrika figyelve: `url_ingest_rejections_total`.
