# assets/

게임이 이 폴더의 PNG·WebP와 지도 데이터를 자동으로 집어 씁니다.
**규격은 상위 폴더의 [`ASSETS.md`](../ASSETS.md) 를 보십시오.**

| 파일 | 최종 크기 | 한 칸 | 상태 |
|---|---|---|---|
| `terrain.png` | 176×44 | 44×44 | ✅ 적용 |
| `icons.png` | 256×32 | 32×32 | ✅ 적용 |
| `flags.png` | 144×32 | 48×32 | ✅ 적용 |
| `portraits.png` | 512×128 | 64×64 | ✅ 적용 |
| `ui_frame.png` | 576×64 | 192×64 | ✅ 적용 |
| `map_geo.js` | 약 170KB | 42개 지방 벡터 | ✅ 적용 |
| `east_asia_relief.webp` | 888×480 | 동아시아 음영 지형 | ✅ 적용 |

제작: Codex. 재생성 도구는 [`../tools/generate_assets.py`](../tools/generate_assets.py),
아트 지침은 [`../tools/ART_DIRECTION.md`](../tools/ART_DIRECTION.md) 에 있습니다.

지도 벡터는 Natural Earth 5.1.2의 공개 도메인 행정구역 자료를
[`../tools/generate_map_geo.py`](../tools/generate_map_geo.py) 로 묶어 만들었습니다.
음영 지형은 Natural Earth II 3.2.0을
[`../tools/generate_relief.py`](../tools/generate_relief.py) 로 같은 투영에 맞췄습니다.

파일이 없으면 코드로 그린 임시 그림으로 돌아갑니다. 한 장씩 따로 넣어도 됩니다.
넣은 뒤 브라우저 콘솔에서 `assetStatus()` 로 확인하십시오.

**한자는 쓰지 마십시오.** 글자가 필요하면 한글로.
