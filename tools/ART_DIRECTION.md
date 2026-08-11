# 에셋 아트 방향

최종 PNG는 `ASSETS.md`의 픽셀 규격에 맞춰 `generate_assets.py`가 결정론적으로 그립니다. 작은 화면에서 읽히도록 세부 묘사보다 실루엣, 낮은 대비, 얇은 먹선을 우선했습니다.

## 방향

- 담백한 조선 고지도 채색과 한지 섬유
- 지도는 위에서 내려다본 무원근 평면
- 지형 위에 세력색이 덮여도 구분되는 낮은 채도
- 어두운 HUD에서 18px로 줄여도 읽히는 아이콘
- 왕조명이 바뀌어도 사용할 수 있는 문자 없는 세력 문양
- 화려한 판타지 금박, 한자, 특정 실존 인물 초상은 사용하지 않음

## 이미지 생성 참고 보드

최종 스프라이트를 자동 생성 이미지에서 잘라 쓰지 않았습니다. 아래 프롬프트로 내장 ImageGen에서 분위기 참고 보드 1장을 만든 뒤, 정확한 셀과 알파는 코드로 다시 그렸습니다.

```text
Use case: stylized-concept
Asset type: visual style reference for 2D grand-strategy game terrain and UI sprites
Primary request: a polished art-direction board for an East Asia historical strategy game spanning Joseon to modernity, emphasizing early Joseon visual language
Subject: four clearly separated top-down terrain studies — pale rice-field plain, low ochre hills, layered dark ink mountain ridges, and muted coast with sand and fine ripples — plus small supporting studies of brass resource emblems and anonymous Joseon court-official portrait silhouettes
Style/medium: restrained Joseon map painting and minhwa-inspired gouache on aged hanji; delicate pale ink outlines; flat orthographic top-down terrain; calm archival museum feel
Composition/framing: square style board, neat visual studies with generous breathing room; terrain swatches are the primary focus
Color palette: plain #5d6b45, hill #6a6247, mountain #585349, coast #4f6459, sea #101820, brass #e0bd76, paper #e8e1d1
Materials/textures: subtle hanji fiber and dry-brush ink, no glossy rendering
Constraints: no text, no letters, no Chinese characters, no numbers, no logos, no flags, no watermark; no fantasy gold foil; no perspective view; no photorealism; no gradients; do not imitate any existing game UI exactly
```
