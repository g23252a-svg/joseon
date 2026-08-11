# assets/

여기에 PNG를 놓으면 게임이 자동으로 씁니다.
**규격은 상위 폴더의 [`ASSETS.md`](../ASSETS.md) 를 보십시오.**

| 파일 | 최종 크기 | 한 칸 | 상태 |
|---|---|---|---|
| `map_geo.js` | 약 125KB | 26개 Path2D 권역 | ☑ |
| `terrain.png` | 176×44 | 44×44 | ☑ |
| `icons.png` | 256×32 | 32×32 | ☑ |
| `flags.png` | 144×32 | 48×32 | ☑ |
| `portraits.png` | 512×128 | 64×64 | ☑ |
| `ui_frame.png` | 576×64 | 192×64 | ☑ |

파일이 없으면 코드로 그린 임시 그림을 씁니다. 한 장씩 따로 넣어도 됩니다.
넣은 뒤 브라우저 콘솔에서 `assetStatus()` 로 확인하십시오.

**한자는 쓰지 마십시오.** 글자가 필요하면 한글로.

원본 시트는 `tools/generate_assets.py`로 같은 결과를 다시 만들 수 있습니다.

`map_geo.js`는 Natural Earth 5.1.2의 공개 도메인 1:10m 행정구역을 게임의
26개 권역으로 병합한 벡터 데이터입니다. 원본 GeoJSON은 저장소에 넣지 않으며,
`tools/generate_map_geo.py --admin1 <원본.geojson> --out assets/map_geo.js`로 재생성합니다.
