import os
import re
import zipfile
import sys

from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog
from PySide6.QtCore import QFile, QIODevice, QThread, QCoreApplication, Signal

class SubThread(QThread):
    print_signal = Signal(str)

    def __init__(self, ui_obj):
        super().__init__()
        self.ui_obj = ui_obj
        self.flag_start = False
    
    def run(self):
        # 중복 실행 방지
        if self.flag_start == True:
            return
        
        self.flag_start = True
        path_abs = self.ui_obj.workDirLineEdit.text()

        if path_abs == "":
            QCoreApplication.processEvents()
            self.flag_start = False
            self.printText("경로를 선택하세요")
            return
        
        os.chdir(path_abs)
        self.printText(f"work directory - {os.getcwd()}")
        
        # 폴더들 안의 하위 폴더들 꺼내기
        if self.ui_obj.checkBox_1.isChecked():
            self.printText("====start extract sub contents")
            self.extractContents(path_abs)
        
        # 압축파일들 압축해제
        if self.ui_obj.checkBox_2.isChecked():
            self.printText("====start unzip files")
            failed = self.unzipFiles(path_abs)
            self.printText(f"\n*** fail list ***\n{str(failed)}\n")

            # 압축파일 삭제
            if self.ui_obj.checkBox_2_1.isChecked():
                self.printText("====start delete unziped zip files")
                pass

        # 폴더들 이름의 특정 패턴 텍스트 없애기
        if self.ui_obj.checkBox_3.isChecked():
            self.printText("====start delete text pattern")
            pattern = self.ui_obj.keywordLineEdit.text()

            error = False
            try:
                re.compile(pattern)
            except Exception as e:
                self.printText(f"정규표현식이 아님. {e}")
                error = True
                
            if not error:
                self.deleteTextPattern(path_abs, pattern)

        # 폴더들 이름의 특정 텍스트 없애기
        if self.ui_obj.checkBox_4.isChecked():
            self.printText("====start delete empty folders")
            word_before = self.ui_obj.keywordLineEdit_before.text()
            word_after = self.ui_obj.keywordLineEdit_after.text()
            self.replaceExpression(path_abs, word_before, word_after)

        # 빈 폴더들 삭제
        if self.ui_obj.checkBox_5.isChecked():
            self.printText("====start delete empty folders")
            self.deleteEmptyFolder()

        self.printText("finish\n")
        self.flag_start = False

    # 현재 경로에 있는 폴더, 파일을 리스트 형태로 변환
    def getCurrentContents(self, abs_path=False) -> list[str]:
        current_path = os.getcwd()

        # os.listdir() , os.scandir() => 파일탐색기창 혹은 dir 명령으로 보여지는 폴더 혹은 파일말고도 일반적이지 않은 것들도 보여줌
        # 내가 원하는 건 dir 명령 혹은 파일탐색기에서 보여지는 목록만을 원함
        # 따라서 해당 함수를 쓰지 않고 op.popen("dir /b").read() 등을 통해 실질적인 목록을 구함
        result = os.popen("dir /b").read().split("\n")
        result.remove("")

        # 윈도우 기준으로 영어의 대소문자를 구분하지 않음
        # 따라서 파일, 폴더 이름을 모두 대문자로 바꾸어서 계산
        if abs_path == True:
            for i in range(len(result)):
                result[i] = current_path + "\\" + result[i].upper()
        else:
            for i in range(len(result)):
                result[i] = result[i].upper()

        return result

    # 항목 중복 이름 대처
    # content(이름)를 path에 없는 이름이 되도록 번호를 추가함
    # return : 컨텐츠 이름. 절대경로 아님
    # content : 폴더 혹은 파일 이름. 절대경로 아님
    # compare_path : 절대 경로
    def makeUniqueName(self, content:str, compare_path:str) -> str:
        count = 0 # 추가 번호용
        new_name = content

        while True:
            if new_name[-1] == ".":
                new_name = new_name[:-1]
            else:
                break
        # 영어 대문자로 변경 - 영어 대소문자를 구분하지 않음
        new_name = new_name.upper()

        # 이미 작업 경로를 바꾼 상태이기 때문에 현재 작업경로를 저장할 필요가 있음
        pwd = os.getcwd()
        
        if compare_path != pwd:
            os.chdir(compare_path)

        compare_list = os.popen("dir /b").read().split("\n")

        # 영어를 대문자로 변경
        for i in range(len(compare_list)):
            compare_list[i] = compare_list[i].upper()

        while True:
            # 비교 경로에 현재 컨텐츠 이름이 존재한다면 번호 증가
            if new_name in compare_list:
                count += 1
            else:# 중복이 없으면 종료
                break

            if os.path.isfile(content):
                name, extension = os.path.splitext(content)#문자열에서 이름과 확장자 분리
                new_name = f"{name} ({count}){extension}"
            elif os.path.isdir(content):
                new_name = f"{content} ({count})"

        if compare_path != pwd:
            os.chdir(pwd)

        return new_name

    # path에 존재하는 zip 파일 압축 풀기 및 동명의 폴더 생성
    def unzipFiles(self, path:str) -> list[str]:
        current_contents = self.getCurrentContents()

        fail_list = []

        for content in current_contents:
            if zipfile.is_zipfile(content):#진짜 zip 파일인지 확인필요
                try:
                    zip_file = zipfile.ZipFile(content, 'r', metadata_encoding='euc-kr')
                except Exception as e:
                    self.printText(f"zipfile initialize error {e}. file name : {content}")
                    fail_list.append(content)
                    continue

                file_name, extension = os.path.splitext(content)
                new_name = self.makeUniqueName(file_name.strip(), path)# ' .zip' 와 같은 이름이 있을 수 있음. 근데 경로 마지막에 공백은 불가능. 따라서 공백 처리
                try:
                    zip_file.extractall(new_name)#새로운 경로에 압축해제. 일반적으로 생각하는 압축해제
                    self.printText(f"unzip file : {content} => {new_name}")
                except Exception as e:
                    self.printText(f"extract error {e}. file {content}")
                    fail_list.append(content)

                zip_file.close()
        return fail_list
    
    # path에 존재하는 폴더 아래에 있는 항목들 path와 같은 경로에 꺼내기
    # path = abs path
    def extractContents(self, path:str) -> None:
        # path에 존재하는 항목 리스트 얻기
        current_contents = self.getCurrentContents()

        for content in current_contents:
            if os.path.isdir(content): # 폴더만 작업
                self.printText(f"폴더 이름 - {content}")
                os.chdir(content)# 폴더 내부로 이동
                sub_contents = self.getCurrentContents()

                for sub_content in sub_contents:
                    new_name = self.makeUniqueName(sub_content, path)

                    if sub_content != new_name:
                        os.rename(sub_content, new_name)# 이름 바꾸기
                    os.popen(f'move "{new_name}" ../').read()# 옮기기

                    self.printText(f"move parent directory: {content} -> {new_name}")
                os.chdir("../")

    # path에 존재하는 빈 폴더 삭제 : abs path
    def deleteEmptyFolder(self) -> None:
        current_content = self.getCurrentContents()

        for content in current_content:
            if os.path.isdir(content):
                try:
                    os.rmdir(content)# 하위에 아무것도 없는 폴더를 삭제. 휴지통 이동이 아닌 바로 삭제
                    self.printText(f"empty folder - {content}")
                except Exception as e:
                    continue

    # path에 존재하는 항목 이름에 들어가는 특정 표현 바꾸기
    def replaceExpression(self, path, word, new_word) -> None:
        current_contents = self.getCurrentContents()

        for content in current_contents:
            temp_name = content.replace(word, new_word).strip()
            if temp_name != content:
                new_name = self.makeUniqueName(temp_name, path)
                try:
                    os.rename(content, new_name)
                    self.printText(f"replace : {content} -> {new_name}")
                except Exception as e:
                    self.printText(f"rename error {e}. file {content}")

    # path에 존재하는 이름의 특정 패턴 제거
    # 기본 세팅 - [~] 패턴 없애기
    def deleteTextPattern(self, path, pattern = r"\[(.*?)\]") -> None:
        try:# 정규식 표현이면 그냥 넘어감
            re.compile(pattern)
        except Exception as e:
            self.printText("pattern is not regular pattern")
            return

        current_contents = self.getCurrentContents()
        
        pattern_list = list()
        for content in current_contents:# 제거할 패턴 목록화
            result = re.findall(pattern, content)# 해당 폴더이름에서 부합하는 패턴을 모두 찾음
            pattern_list.extend(result)# 패턴을 리스트에 추가함. [] 는 안 넣어짐
        pattern_list = list(set(pattern_list))# 중복 패턴 없애기

        self.printText(f"pattern 목록\n{pattern_list}\n")

        if pattern_list == []:
            self.printText("일치하는 패턴 없음")
            return
        
        change = False
        for content in current_contents:
            temp_name = content

            for pattern in pattern_list:
                pattern = f"[{pattern}]"

                if pattern in temp_name:
                    change = True
                    temp_name = temp_name.replace(pattern, "").strip()

            if change:
                self.printText(f"preprocess name - {temp_name}")
                new_name = self.makeUniqueName(temp_name, path)
                try:
                    os.rename(content, new_name)
                    self.printText(f"rename {content} -> {new_name}")
                except Exception as e:
                    self.printText(f"rename error {e}. file {content} => new name {new_name}")
                change = False

    def printText(self, text):
        self.print_signal.emit(text)
        print(text)

class MainWindow(QMainWindow):
    def __init__(self):
        self.main_window = self.loadUI("main.ui")
        self.main_window.workDirBtn.clicked.connect(self.selectDirectory)
        self.main_window.startBtn.clicked.connect(self.startProcess)
        self.main_window.checkBox_2.stateChanged.connect(self.changedState)

        self.sub_thread = SubThread(self.main_window)
        self.sub_thread.print_signal.connect(self.updateTextEdit)

        self.main_window.show()

    def loadUI(self, ui_file_name):
        exist_dir = os.path.dirname(__file__)
        ui_file = QFile(exist_dir + "\\" + ui_file_name)

        if not ui_file.open(QIODevice.ReadOnly):
            print(f"Cannot open {ui_file_name}: {ui_file.errorString()}")
            sys.exit(-1)

        loader = QUiLoader()
        window = loader.load(ui_file)
        ui_file.close()

        if not window:
            print(loader.errorString())
            sys.exit(-1)

        return window
    
    def changedState(self):
        state = self.main_window.checkBox_2.checkState()

        if state.value == 2:
            self.main_window.checkBox_2_1.setEnabled(True)
        elif state.value == 0:
            self.main_window.checkBox_2_1.setEnabled(False)
    
    def selectDirectory(self):
        # 폴더 선택
        widget = self.main_window.findChild(QFileDialog, "workDirButton")# QMainWindow를 상속받기 때문에 위젯에 직접 접근
        directory = QFileDialog.getExistingDirectory(widget, "경로 선택", "")

        if not directory == "":
            self.main_window.workDirLineEdit.setText(directory)

    def startProcess(self):
        try:
            self.sub_thread.start()
        except Exception as e:
            print(e)

    def updateTextEdit(self, text):
        self.main_window.textEditViewer.append(text)

app = QApplication(sys.argv)
window = MainWindow()
sys.exit(app.exec())


'''
# todo
delete pattern
# 영어, 한국어 외 언어 대응도 필요함
# f"[{pattern}]" 에서 [] 표현 말고 다른것도 되도록

# 특정 파일 삭제 기능 추가
'''
