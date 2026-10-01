# Personal Cowork 0.1.0

ChatGPT와 Codex에 목표를 맡기면 사용 가능한 도구로 작업을 진행하고, 결과를 확인한 뒤 전달하도록 구성한 개인용 플러그인입니다. Anthropic 또는 OpenAI의 공식 제품이 아닙니다.

## 구현한 기능

- 목표·작업 범위·완료 기준을 정하고 실제 작업을 이어서 수행하는 공통 스킬.
- 기존 파일·브라우저·연결된 앱·전문 스킬을 상황에 맞게 사용하는 지침.
- 작업 단계와 검증 근거를 파일에 저장하고 중단 후 현재 자료를 재확인하는 흐름.
- Python 상태 도구: 근거 없는 완료, 미완료 단계, 실패한 기준, 변경·삭제된 등록 결과물의 완료 처리를 거부.
- 불필요한 전체 파일 재읽기와 중복 작업을 줄이는 지침. 실제 토큰 사용량이나 절감률을 측정하지는 않습니다.

별도의 모델 API, MCP 서버, 계정, 데스크톱 조작 엔진은 포함하지 않습니다. 실제 파일·앱 접근과 작업 실행은 설치한 ChatGPT·Codex 환경의 도구와 권한을 사용합니다. 작업 기록 저장은 백그라운드 실행이나 자동 예약을 시작하지 않습니다.

## Codex에 설치하고 사용하기

저장소를 복제하고 패키지 루트에서 로컬 마켓플레이스와 플러그인을 등록합니다. 이 명령은 Codex의 설치 설정을 변경합니다.

```sh
git clone https://github.com/gunrp0803-droid/personal-cowork.git
cd personal-cowork
codex plugin marketplace add . --json
codex plugin add personal-cowork@personal-cowork-local --json
```

플러그인 대신 프로젝트별 스킬로 사용하려면 해당 프로젝트의 `.agents/skills/personal-cowork`에 이 저장소의 `skills/personal-cowork` 폴더를 복사하거나 심볼릭 링크로 연결합니다. 현재 개발 작업 폴더에서는 이 직접 연결 방식으로 스킬을 사용하며, Codex CLI 0.159.1의 네이티브 탐색에서 `enabled: true`를 확인했습니다. 다른 환경의 설치 상태는 별도로 확인해야 합니다.

Codex에서 스킬 또는 플러그인을 선택해 다음과 같이 요청합니다. 새로 추가한 항목이 선택기에 표시되지 않으면 새 대화를 시작하거나 앱을 다시 여십시오.

```text
$personal-cowork 지정한 폴더의 CSV를 읽고 분류별 합계 보고서를 만들어 주세요.
원본은 보존하고 결과는 outputs에 저장한 뒤 합계를 검증해 주세요.
```

```text
$personal-cowork 이 프로젝트의 로그인 오류를 수정하고 관련 검증까지 진행해 주세요.
수정한 파일과 확인한 결과를 알려 주세요.
```

```text
$personal-cowork work/cowork에 저장된 미완료 작업을 확인하고 이어서 진행해 주세요.
현재 파일을 재확인한 뒤 남은 단계부터 처리해 주세요.
```

플러그인으로 설치하면 선택기에 표시된 포함 스킬을 사용합니다. 같은 이름의 직접 연결 스킬과 플러그인 스킬을 동시에 활성화하면 둘 다 나타날 수 있으므로 한 가지 설치 방식을 선택하십시오.

가상 CSV와 생성 결과는 [지출 예제](examples/spending/README.md)에서 확인할 수 있습니다.

## ChatGPT와 플러그인 형태로 사용하기

루트 `plugin.json`과 `skills/`가 공식 Agent Plugins 형식을 따릅니다. 이 패키지는 ChatGPT와 Codex용 로컬 마켓플레이스에 등록할 수 있습니다. 패키지의 `.agents/plugins/marketplace.json`에는 `personal-cowork-local` 항목이 준비되어 있습니다. Codex의 명시적 `plugin/read`로 패키지 해석을 확인했습니다. 검증 당시 개발 환경에서는 플러그인 자체를 설치하지 않고 스킬을 직접 연결했습니다.

로컬 마켓플레이스를 지원하는 데스크톱 환경에서 Plugins의 로컬 소스를 확인하고 설치한 뒤 새 대화에서 선택합니다. ChatGPT에서는 `@` 메뉴로 설치된 플러그인 또는 스킬을 선택합니다. 실제 계정의 설치 메뉴와 지원 여부는 별도 확인이 필요합니다.

ZIP을 일반 ChatGPT 대화에 첨부하는 것만으로 설치된다고 보장하지 않습니다. 웹에서 조직 또는 공개 배포를 하려면 지원하는 플러그인 생성·배포 절차와 권한이 필요합니다. GitHub 소스 공개와 ChatGPT 플러그인 카탈로그 등록은 별개의 작업입니다. 이 버전에서는 ChatGPT 계정 설치, 외부 서비스 연결, 플러그인 카탈로그 게시를 수행하지 않았습니다.

다른 위치에 압축을 풀어 설치할 수 있도록 패키지 안에도 `.agents/plugins/marketplace.json`을 포함했습니다. 이 파일의 로컬 소스는 패키지 루트 `.`입니다.

ZIP에서 설치할 때도 압축을 푼 `personal-cowork` 폴더에서 위와 같은 마켓플레이스 등록·설치 명령을 실행합니다.

## 상태 저장 도구와 검증

Python 3.9 이상이 필요하며 추가 라이브러리는 사용하지 않습니다.

```sh
python3 skills/personal-cowork/scripts/task_state.py --help
python3 -m unittest discover -s tests -v
```

상태 도구는 `init`, `show`, `step`, `check`, `artifact`, `finish` 명령을 제공합니다. 실행 예시는 [작업 상태 안내](skills/personal-cowork/references/task-state.md)에 있습니다. `init`은 기존 워크스페이스 안에 `work/cowork/<ID>/task.json`을 생성합니다. 완료한 작업은 변경할 수 없으므로 후속 수정은 새 작업으로 진행합니다. 작업마다 한 작성자만 상태를 수정합니다.

`finish`는 기록과 파일 해시를 확인합니다. 보고서 계산이 맞는지, 코드가 올바른지, 외부 앱에 저장됐는지까지 자동 판단하지 않습니다. 실행한 에이전트가 실제 검증을 수행하고 근거를 기록해야 합니다.

## 공식 형식 참고

- [플러그인 패키지 형식](https://developers.openai.com/plugins/build/plugins)
- [Codex 로컬 스킬 탐색](https://learn.chatgpt.com/docs/build-skills)
- [플러그인 설치](https://learn.chatgpt.com/docs/plugins)
- [외부 배포와 검토](https://developers.openai.com/plugins/deploy/submission)

검증 결과와 실사용 테스트의 범위는 [검증결과.md](검증결과.md)를 참고하십시오.

## 개발 업데이트

이 프로젝트에서 요청한 업데이트는 관련 검증을 마친 뒤 커밋·푸시합니다. 작업 기준은 [AGENTS.md](AGENTS.md)에 기록했습니다. 실행 중 생성한 작업 기록·개인 입력·출력과 인증 정보는 공개 소스에 포함하지 않습니다.
