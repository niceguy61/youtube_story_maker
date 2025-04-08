import gradio as gr
import boto3
import re
import json
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경 변수에서 AWS 설정 가져오기
AWS_PROFILE = os.getenv("AWS_PROFILE", "sso")  # 기본값 "sso"
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")  # 기본값 "ap-northeast-2"
MODEL_ID = os.getenv("MODEL_ID", "apac.anthropic.claude-3-5-sonnet-20241022-v2:0")  # 기본값 Claude 3.5 Sonnet

session = boto3.Session(profile_name='sso')
# Initialize AWS Bedrock client
bedrock = session.client(
    service_name='bedrock-runtime',
    region_name='ap-northeast-2'
)

def count_korean_chars(text):
    """한글 글자수를 세는 함수 (공백, 특수문자 제외)"""
    text = re.sub(r'[^가-힣]', '', text)
    return len(text)

def invoke_bedrock(prompt, max_retries=3):
    """Bedrock API 호출 with retry logic"""
    for attempt in range(max_retries):
        try:
            response = bedrock.invoke_model(
                modelId="apac.anthropic.claude-3-5-sonnet-20241022-v2:0",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )
            response_body = json.loads(response.get('body').read().decode('utf-8'))
            return response_body['content'][0]['text']
        except Exception as e:
            if attempt == max_retries - 1:
                raise gr.Error(f"API 호출 실패: {str(e)}")
            continue

def analyze_script(script):
    """대본 분석을 위한 Claude 호출"""
    prompt = f"""아래 대본을 분석해주세요:
    1. 등장인물 목록과 특징
    2. 스토리의 기승전결 구조
    3. 주요 내러티브와 테마
    
    대본:
    {script}
    
    분석 결과는 마크다운 형식으로 깔끔하게 정리해주세요."""
    
    return invoke_bedrock(prompt)

def generate_modified_story(original_analysis, user_suggestions):
    """사용자 제안사항을 반영한 새로운 스토리 생성"""
    prompt = f"""원본 분석:
    {original_analysis}
    
    사용자 제안사항:
    {user_suggestions}
    
    위 내용을 바탕으로 수정된 이야기를 제안해주세요.
    결과는 마크다운 형식으로 깔끔하게 정리해주세요."""
    
    return invoke_bedrock(prompt)

def generate_intro(word_count=2500):
    """기 파트 생성"""
    # 추가 지시사항이 있는 경우 포함
    additional_instruction = ""
    if state.additional_instruction:
        additional_instruction = f"\n\n추가 지시사항:\n{state.additional_instruction}"
    
    prompt = f"""원본 대본 분석:
{state.analysis}

수정된 스토리 제안:
{state.modified_story}{additional_instruction}

위 내용을 바탕으로 이야기의 '기' 부분을 작성해주세요.

요구사항:
1. 한글 기준 {word_count-200}-{word_count+200}자 (공백, 특수문자 제외)
2. 원본 분석과 수정된 스토리 제안을 반영하여 작성
3. 인물, 배경, 세계관 소개
4. 상황과 문제 제시
5. 독자의 관심을 끄는 도입부

'기' 파트를 작성해주세요."""

    content = invoke_bedrock(prompt)
    char_count = count_korean_chars(content)
    
    # 글자수 조정 (필요 시)
    retry_count = 0
    max_retries = 2
    
    while not (word_count-200 <= char_count <= word_count+200) and retry_count < max_retries:
        adjust = "줄여서" if char_count > word_count+200 else "늘려서"
        prompt = f"""이전 내용을 {adjust} 정확히 {word_count-200}-{word_count+200}자 사이로 조정해주세요.
        현재 글자수: {char_count}
        목표 글자수: {word_count}
        
        내용:
        {content}"""
        content = invoke_bedrock(prompt)
        char_count = count_korean_chars(content)
        retry_count += 1
    
    return content, char_count

def generate_development(word_count=2500):
    """승 파트 생성"""
    # 추가 지시사항이 있는 경우 포함
    additional_instruction = ""
    if state.additional_instruction:
        additional_instruction = f"\n\n추가 지시사항:\n{state.additional_instruction}"
    
    prompt = f"""원본 대본 분석:
{state.analysis}

수정된 스토리 제안:
{state.modified_story}

기 파트 내용:
{state.final_story['기']}{additional_instruction}

위 내용을 바탕으로 이야기의 '승' 부분을 작성해주세요.

요구사항:
1. 한글 기준 {word_count-200}-{word_count+200}자 (공백, 특수문자 제외)
2. 기 파트의 내용과 자연스럽게 연결
3. 갈등과 문제의 심화
4. 인물들의 행동과 반응
5. 긴장감 조성

'승' 파트를 작성해주세요."""

    content = invoke_bedrock(prompt)
    char_count = count_korean_chars(content)
    
    # 글자수 조정 (필요 시)
    retry_count = 0
    max_retries = 2
    
    while not (word_count-200 <= char_count <= word_count+200) and retry_count < max_retries:
        adjust = "줄여서" if char_count > word_count+200 else "늘려서"
        prompt = f"""이전 내용을 {adjust} 정확히 {word_count-200}-{word_count+200}자 사이로 조정해주세요.
        현재 글자수: {char_count}
        목표 글자수: {word_count}
        
        내용:
        {content}"""
        content = invoke_bedrock(prompt)
        char_count = count_korean_chars(content)
        retry_count += 1
    
    return content, char_count

def generate_turn(word_count=2500):
    """전 파트 생성"""
    # 추가 지시사항이 있는 경우 포함
    additional_instruction = ""
    if state.additional_instruction:
        additional_instruction = f"\n\n추가 지시사항:\n{state.additional_instruction}"
    
    # 기 파트 요약
    gi_summary = ""
    if state.final_story['기']:
        words = state.final_story['기'].split()
        gi_summary = " ".join(words[:min(100, len(words))]) + "..."
    
    prompt = f"""기 파트 내용 요약:
{gi_summary}

승 파트 내용:
{state.final_story['승']}{additional_instruction}

위 내용을 바탕으로 이야기의 '전' 부분을 작성해주세요.

요구사항:
1. 한글 기준 {word_count-200}-{word_count+200}자 (공백, 특수문자 제외)
2. 승 파트의 내용과 자연스럽게 연결
3. 극적인 반전이나 전환점 포함
4. 인물의 중요한 결정이나 깨달음
5. 이야기의 방향 전환

'전' 파트를 작성해주세요."""

    content = invoke_bedrock(prompt)
    char_count = count_korean_chars(content)
    
    # 글자수 조정 (필요 시)
    retry_count = 0
    max_retries = 2
    
    while not (word_count-200 <= char_count <= word_count+200) and retry_count < max_retries:
        adjust = "줄여서" if char_count > word_count+200 else "늘려서"
        prompt = f"""이전 내용을 {adjust} 정확히 {word_count-200}-{word_count+200}자 사이로 조정해주세요.
        현재 글자수: {char_count}
        목표 글자수: {word_count}
        
        내용:
        {content}"""
        content = invoke_bedrock(prompt)
        char_count = count_korean_chars(content)
        retry_count += 1
    
    return content, char_count

def generate_conclusion(word_count=2500):
    """결 파트 생성"""
    # 추가 지시사항이 있는 경우 포함
    additional_instruction = ""
    if state.additional_instruction:
        additional_instruction = f"\n\n추가 지시사항:\n{state.additional_instruction}"
    
    prompt = f"""전 파트 내용:
{state.final_story['전']}{additional_instruction}

위 내용을 바탕으로 이야기의 '결' 부분을 작성해주세요.

요구사항:
1. 한글 기준 {word_count-200}-{word_count+200}자 (공백, 특수문자 제외)
2. 전 파트의 내용과 자연스럽게 연결
3. 모든 갈등과 문제의 해결
4. 캐릭터 아크의 완성
5. 이야기의 주제와 메시지를 강조하는 마무리

'결' 파트를 작성해주세요."""

    content = invoke_bedrock(prompt)
    char_count = count_korean_chars(content)
    
    # 글자수 조정 (필요 시)
    retry_count = 0
    max_retries = 2
    
    while not (word_count-200 <= char_count <= word_count+200) and retry_count < max_retries:
        adjust = "줄여서" if char_count > word_count+200 else "늘려서"
        prompt = f"""이전 내용을 {adjust} 정확히 {word_count-200}-{word_count+200}자 사이로 조정해주세요.
        현재 글자수: {char_count}
        목표 글자수: {word_count}
        
        내용:
        {content}"""
        content = invoke_bedrock(prompt)
        char_count = count_korean_chars(content)
        retry_count += 1
    
    return content, char_count

# 각 파트 생성 함수 (UI 이벤트 핸들러용)
def create_intro():
    try:
        print("'기' 파트 생성 중...")
        content, char_count = generate_intro(state.word_counts['기'])
        state.final_story['기'] = content
        return content, f"{char_count}자"
    except Exception as e:
        print(f"'기' 파트 생성 중 오류: {str(e)}")
        return "생성 중 오류가 발생했습니다.", "오류"

def create_development():
    if not state.final_story['기']:
        return "먼저 '기' 파트를 생성해주세요.", "대기 중"
    
    try:
        print("'승' 파트 생성 중...")
        content, char_count = generate_development(state.word_counts['승'])
        state.final_story['승'] = content
        return content, f"{char_count}자"
    except Exception as e:
        print(f"'승' 파트 생성 중 오류: {str(e)}")
        return "생성 중 오류가 발생했습니다.", "오류"

def create_turn():
    if not state.final_story['승']:
        return "먼저 '승' 파트를 생성해주세요.", "대기 중"
    
    try:
        print("'전' 파트 생성 중...")
        content, char_count = generate_turn(state.word_counts['전'])
        state.final_story['전'] = content
        return content, f"{char_count}자"
    except Exception as e:
        print(f"'전' 파트 생성 중 오류: {str(e)}")
        return "생성 중 오류가 발생했습니다.", "오류"

def create_conclusion():
    if not state.final_story['전']:
        return "먼저 '전' 파트를 생성해주세요.", "대기 중"
    
    try:
        print("'결' 파트 생성 중...")
        content, char_count = generate_conclusion(state.word_counts['결'])
        state.final_story['결'] = content
        return content, f"{char_count}자"
    except Exception as e:
        print(f"'결' 파트 생성 중 오류: {str(e)}")
        return "생성 중 오류가 발생했습니다.", "오류"

# State management class
class StoryState:
    def __init__(self):
        self.analysis = None
        self.modified_story = None
        self.final_story = {'기': '', '승': '', '전': '', '결': ''}
        self.current_step = 1
        self.original_script = None  # Store original script
        self.word_counts = {'기': 2500, '승': 2500, '전': 2500, '결': 2500}  # 각 파트별 글자수 설정
        self.additional_instruction = ""  # 추가 지시사항 저장 변수
        
    def reset(self):
        """Reset state while keeping original script"""
        script = self.original_script
        word_counts = self.word_counts
        additional_instruction = self.additional_instruction
        self.__init__()
        self.original_script = script
        self.word_counts = word_counts
        self.additional_instruction = additional_instruction

state = StoryState()

def process_script(script):
    if not script.strip():
        raise gr.Error("대본을 입력해주세요.")
    
    # Store original script and analyze
    state.original_script = script
    state.analysis = analyze_script(script)
    state.current_step = 2
    
    return (
        state.analysis,
        gr.update(visible=True),
        state.analysis,  # 피드백 화면의 분석 결과 표시 컴포넌트에도 전달
        gr.update(visible=False)
    )

def process_feedback(feedback):
    if not feedback.strip():
        raise gr.Error("피드백을 입력해주세요.")
    state.modified_story = generate_modified_story(state.analysis, feedback)
    state.current_step = 3
    return (
        state.modified_story,
        gr.update(visible=True),  # modified_story_heading
        gr.update(visible=True),  # modified_story_output
        gr.update(visible=True)   # proceed_to_generation_btn
    )

# 슬라이더 값 변경 시 상태 업데이트 함수
def update_word_count(intro, dev, turn, end):
    state.word_counts['기'] = intro
    state.word_counts['승'] = dev
    state.word_counts['전'] = turn
    state.word_counts['결'] = end
    return f"설정된 총 글자수: {intro + dev + turn + end}자"

# 추가 지시사항 업데이트 함수
def update_instruction(instruction):
    """추가 지시사항 업데이트"""
    state.additional_instruction = instruction
    return f"지시사항이 업데이트되었습니다: {len(instruction)}자"

# UI 구성
with gr.Blocks(title="대본 분석 및 스토리 생성기") as demo:
    # 큐 설정
    demo.queue()
    gr.Markdown("# 대본 분석 및 스토리 생성기")
    
    # Step 1: Script Analysis
    with gr.Group():
        input_script = gr.Textbox(label="분석할 대본을 입력하세요", lines=10)
        analyze_btn = gr.Button("분석 시작")
        analysis_output = gr.Markdown(visible=False)
    
    # Step 2: Feedback
    with gr.Group(visible=False) as feedback_box:
        # 분석 결과 다시 표시
        gr.Markdown("## 대본 분석 결과")
        analysis_display = gr.Markdown()  # Step 1의 분석 결과를 여기에 표시
        
        gr.Markdown("## 피드백 입력")
        feedback_input = gr.Textbox(label="변경하고 싶은 내용을 입력하세요", lines=5, 
                                    placeholder="예: '주인공의 성격을 더 용감하게 바꿔주세요' 또는 '스토리의 배경을 현대로 바꿔주세요'")
        feedback_btn = gr.Button("피드백 제출")
        
        # 명확한 변수 할당 방식 사용
        modified_story_heading = gr.Markdown(value="## 수정된 스토리 제안", visible=False)
        modified_story_output = gr.Markdown(visible=False)
        
        # 수정 후 최종 스토리 생성으로 진행하는 버튼
        proceed_to_generation_btn = gr.Button("스토리 생성 시작", visible=False)
    
    # Step 3: Final Story Generation
    with gr.Group(visible=False) as final_box:
        gr.Markdown("## 추가 지시사항")
        instruction_input = gr.Textbox(
            label="스토리 생성 시 반영할 추가 지시사항을 입력하세요", 
            lines=3,
            placeholder="예: '주인공이 마지막에 희생하는 결말로 해주세요' 또는 '사투리를 사용하는 캐릭터를 추가해주세요'"
        )
        instruction_btn = gr.Button("지시사항 적용")
        instruction_status = gr.Textbox(label="지시사항 상태", value="입력된 지시사항이 없습니다.")
        
        gr.Markdown("## 글자수 설정")
        
        with gr.Row():
            # 각 파트별 글자수 설정 슬라이더
            with gr.Column():
                gr.Markdown("### 기")
                intro_slider = gr.Slider(minimum=500, maximum=3500, value=2500, step=100, 
                                        label="글자수 설정", info="500-3500자 사이로 설정하세요")
            
            with gr.Column():
                gr.Markdown("### 승")
                dev_slider = gr.Slider(minimum=500, maximum=3500, value=2500, step=100, 
                                      label="글자수 설정", info="500-3500자 사이로 설정하세요")
            
            with gr.Column():
                gr.Markdown("### 전")
                turn_slider = gr.Slider(minimum=500, maximum=3500, value=2500, step=100, 
                                       label="글자수 설정", info="500-3500자 사이로 설정하세요")
            
            with gr.Column():
                gr.Markdown("### 결")
                end_slider = gr.Slider(minimum=500, maximum=3500, value=2500, step=100, 
                                      label="글자수 설정", info="500-3500자 사이로 설정하세요")
        
        # 총 글자수 표시
        total_word_count = gr.Textbox(label="총 글자수", value="설정된 총 글자수: 10000자")
        
        # 슬라이더 변경 이벤트 연결
        intro_slider.change(
            update_word_count, 
            inputs=[intro_slider, dev_slider, turn_slider, end_slider], 
            outputs=[total_word_count]
        )
        dev_slider.change(
            update_word_count, 
            inputs=[intro_slider, dev_slider, turn_slider, end_slider], 
            outputs=[total_word_count]
        )
        turn_slider.change(
            update_word_count, 
            inputs=[intro_slider, dev_slider, turn_slider, end_slider], 
            outputs=[total_word_count]
        )
        end_slider.change(
            update_word_count, 
            inputs=[intro_slider, dev_slider, turn_slider, end_slider], 
            outputs=[total_word_count]
        )
        
        gr.Markdown("## 스토리 생성")
        gr.Markdown("각 파트를 순서대로 생성하세요 (기 → 승 → 전 → 결)")
        
        with gr.Row():
            # 각 파트별 독립 생성 버튼
            intro_btn = gr.Button("기 생성")
            dev_btn = gr.Button("승 생성")
            turn_btn = gr.Button("전 생성")
            end_btn = gr.Button("결 생성")
        
        with gr.Tabs() as story_tabs:
            with gr.TabItem("기"):
                gr.Markdown("## 기")
                intro_count = gr.Textbox(label="글자수")
                intro_content = gr.Markdown()
            
            with gr.TabItem("승"):
                gr.Markdown("## 승")
                dev_count = gr.Textbox(label="글자수")
                dev_content = gr.Markdown()
                
            with gr.TabItem("전"):
                gr.Markdown("## 전")
                turn_count = gr.Textbox(label="글자수")
                turn_content = gr.Markdown()
                
            with gr.TabItem("결"):
                gr.Markdown("## 결")
                end_count = gr.Textbox(label="글자수")
                end_content = gr.Markdown()
    
    # Event handlers
    analyze_btn.click(
        process_script,
        inputs=input_script,
        outputs=[analysis_output, feedback_box, analysis_display, gr.Textbox()],
        api_name="analyze_script"
    )
    
    feedback_btn.click(
        process_feedback,
        inputs=[feedback_input],
        outputs=[
            modified_story_output,
            modified_story_heading,
            modified_story_output,
            proceed_to_generation_btn
        ],
        api_name="process_feedback"
    )
    
    # 스토리 생성 시작 버튼 이벤트
    proceed_to_generation_btn.click(
        lambda: gr.update(visible=True),
        inputs=[],
        outputs=[final_box],
        api_name="show_final_box"
    )
    
    # 각 파트별 생성 버튼 이벤트
    intro_btn.click(
        create_intro,
        outputs=[intro_content, intro_count],
        api_name="create_intro"
    )
    
    dev_btn.click(
        create_development,
        outputs=[dev_content, dev_count],
        api_name="create_development"
    )
    
    turn_btn.click(
        create_turn,
        outputs=[turn_content, turn_count],
        api_name="create_turn"
    )
    
    end_btn.click(
        create_conclusion,
        outputs=[end_content, end_count],
        api_name="create_conclusion"
    )

    instruction_btn.click(
        update_instruction,
        inputs=[instruction_input],
        outputs=[instruction_status],
        api_name="update_instruction"
    )

if __name__ == "__main__":
    # Enable sharing and configure for continuous session
    demo.launch(
        share=True,
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True
    )