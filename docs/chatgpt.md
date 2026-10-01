# ChatGPT Chat와 Work에서 사용하기

설치된 스킬형 플러그인은 ChatGPT의 일반 Chat과 Work에서 사용할 수 있습니다. 로컬 Codex의 `.agents/skills` 연결과 ChatGPT 계정 설치는 서로 다른 절차입니다. GitHub 저장소를 공개한 것만으로 ChatGPT 플러그인 디렉터리에 등록되지는 않습니다. [공식 플러그인 안내](https://learn.chatgpt.com/docs/plugins).

## Plugin Creator로 개인 워크플로 만들기

Plugin Creator가 계정·워크스페이스에 제공되고 플러그인 사용 권한이 있을 때 사용할 수 있는 경로입니다. 현재 계정에서 실제 생성·설치·실행했는지는 별도로 확인해야 합니다. [공식 생성 절차](https://learn.chatgpt.com/docs/build-plugins).

1. 저장소 루트에서 `python3 scripts/build_packages.py`를 실행합니다. `dist/personal-cowork-chatgpt-context-0.2.0.md`가 공통 스킬과 상태 도구 안내를 담은 단일 자료 파일로 생성됩니다.
2. ChatGPT의 새 Chat 또는 Work에서 `@`를 입력하고 메뉴의 **Plugin Creator**를 선택합니다.
3. 생성한 Markdown 파일을 작업 지침 자료로 첨부하고 다음 요청을 보냅니다. 일반 첨부는 생성 과정의 자료 제공이며 자동 설치가 아닙니다.

```text
Personal Cowork라는 개인용 플러그인을 만들어 주세요.
첨부한 Markdown의 공통 스킬 지침을 기준으로,
사용자가 맡긴 작업을 실행하고 결과를 검증하는 흐름을 구성해 주세요.

일반 Chat과 Work에서 현재 제공되는 도구에 맞게 동작해야 합니다.
실행 도구나 저장 공간이 없으면 대화 안에서 진행 상태와 인계 내용을 정리하고,
파일 저장이나 Python 검증을 실행한 것처럼 표시하지 마세요.
이 플러그인을 만드는 것만으로 새로운 앱·파일 접근 권한을 추가하지 마세요.

이름, 설명, 지침을 검토할 수 있도록 보여 주고
제 계정에서 설치를 마치는 절차를 안내해 주세요.
```

4. 생성 결과와 설치 안내를 확인합니다. 설치된 플러그인을 새 Chat과 새 Work 각각의 `@` 메뉴에서 선택해 아래 예제를 테스트합니다. 설치 메뉴나 Plugin Creator가 없으면 계정에서 이 경로를 지원하는지 먼저 확인해야 합니다.

## Chat과 Work에서 각각 확인할 예제

아래 CSV를 붙여 넣거나 저장소의 `examples/spending/inputs/spending.csv`를 첨부합니다. 설치한 Personal Cowork를 선택한 뒤 요청합니다.

```text
분류별 지출을 집계하고 합계를 검증해 주세요.
실제 파일 생성 도구가 있으면 보고서 파일을 만들어 주세요.
없으면 검증한 보고서를 이 대화에 작성해 주세요.

category,amount_krw
식비,6500
식비,8000
학습,15000
교통,3200
교통,2100
식비,9000
학습,12000
```

정답은 식비 23,500원, 학습 27,000원, 교통 5,300원, 전체 55,800원입니다. 각 대화에서 플러그인이 선택되었는지, 결과가 맞는지, 실제 제공된 도구만 사용했는지 확인합니다. 한 모드에서의 성공을 다른 모드의 실행 증거로 기록하지 않습니다.

## 다른 설치 경로

- **스킬 업로드가 제공되는 계정:** Plugins → Skills → Create → Upload from your computer. 공식 안내의 대상은 적격 Business·Enterprise·Healthcare·Edu 사용자이며 워크스페이스 설정에 영향을 받습니다. 업로드 창이 허용하는 형식을 따르십시오. 함께 생성하는 스킬 ZIP의 해당 계정 업로드 승인은 아직 검증하지 않았습니다. [공식 스킬 안내](https://help.openai.com/en/articles/20001066-skills-in-chatgpt).
- **워크스페이스 관리자:** Admin → Plugins에서 GitHub 마켓플레이스를 가져올 수 있습니다. 소스는 `https://github.com/gunrp0803-droid/personal-cowork`, 브랜치는 `main`이며 저장소 루트의 `.agents/plugins/marketplace.json`을 사용합니다. 사용자 역할과 관리 권한이 필요한 경로입니다. [공식 가져오기 안내](https://learn.chatgpt.com/docs/enterprise/plugin-management).
- **생성·설치 메뉴가 없는 계정:** 생성한 Markdown을 지침 자료로 붙여 넣거나 첨부하여 현재 대화에서 같은 작업 절차를 요청할 수 있습니다. 이 방식은 플러그인 설치·자동 활성화·다른 대화의 상태 보관을 의미하지 않습니다.

## 환경에 따른 동작

| 환경 | 사용하는 자료와 도구 | 상태 저장 |
|---|---|---|
| 일반 Chat | 제공한 텍스트·업로드·현재 대화에서 허용한 도구 | 실행·파일 도구가 없으면 대화 안의 진행 기록과 인계 |
| Work Cloud | 현재 클라우드 작업 공간·업로드·연결된 도구 | 쓰기 공간과 실행 가능한 상태 스크립트가 있을 때 파일 기록 |
| 로컬 Work 또는 Codex | 허용된 로컬 작업 공간과 실행 도구 | Python·쓰기 공간·실제 스크립트가 있으면 상태 도구 사용 |

모드 이름만으로 도구 제공 여부를 판단하지 않습니다. 로컬 Codex의 설정과 파일 경로를 Work Cloud가 자동 상속한다고 가정하지 않습니다. [ChatGPT 사용 환경](https://learn.chatgpt.com/docs/use-chatgpt).

## 업데이트 적용

GitHub의 소스 업데이트와 기존 ChatGPT 플러그인의 지침 갱신은 별개입니다. Plugin Creator로 만든 플러그인은 최신 Markdown을 다시 생성해 제공하고 기존 플러그인의 지침 수정 절차를 따라야 합니다. 관리자가 가져온 GitHub 마켓플레이스는 해당 워크스페이스의 동기화 절차를 사용합니다. 커밋·푸시만으로 모든 계정에 최신 지침이 반영됐다고 표시하지 않습니다.
