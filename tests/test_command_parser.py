from app.commands.command import CommandType
from app.commands.parser import CommandParser


parser = CommandParser()


def test_parse_join():
    command = parser.parse("참가")

    assert command.type == CommandType.JOIN
    assert command.amount == 0


def test_parse_start():
    command = parser.parse("시작")

    assert command.type == CommandType.START
    assert command.amount == 0


def test_parse_call():
    command = parser.parse("콜")

    assert command.type == CommandType.CALL
    assert command.amount == 0


def test_parse_check():
    command = parser.parse("체크")

    assert command.type == CommandType.CHECK
    assert command.amount == 0


def test_parse_fold():
    command = parser.parse("폴드")

    assert command.type == CommandType.FOLD
    assert command.amount == 0


def test_parse_raise():
    command = parser.parse("레이즈 600")

    assert command.type == CommandType.RAISE
    assert command.amount == 600


def test_parse_raise_with_invalid_amount():
    try:
        parser.parse("레이즈 abc")
        assert False
    except ValueError as e:
        assert "레이즈 금액은 숫자로 입력해야 합니다" in str(e)


def test_parse_unknown_command():
    try:
        parser.parse("몰라")
        assert False
    except ValueError as e:
        assert "알 수 없는 명령어입니다" in str(e)

def test_parse_all_in():
    command = parser.parse("올인")

    assert command.type == CommandType.ALL_IN
    assert command.amount == 0

def test_parse_all_in_with_fss_mention():
    command = parser.parse("FSS 올인")

    assert command.type == CommandType.ALL_IN
    assert command.amount == 0

def test_parse_help():
    command = parser.parse("도움말")

    assert command.type == CommandType.HELP
    assert command.amount == 0


def test_parse_help_with_fss_mention():
    command = parser.parse("FSS 도움말")

    assert command.type == CommandType.HELP
    assert command.amount == 0


def test_parse_reset():
    command = parser.parse("리셋")

    assert command.type == CommandType.RESET
    assert command.amount == 0


def test_parse_reset_with_fss_mention():
    command = parser.parse("FSS 리셋")

    assert command.type == CommandType.RESET
    assert command.amount == 0

def test_parse_ranking():
    command = parser.parse("랭킹")

    assert command.type == CommandType.RANKING
    assert command.amount == 0


def test_parse_record():
    command = parser.parse("전적")

    assert command.type == CommandType.RECORD
    assert command.amount == 0

def test_parse_new_tournament():
    command = parser.parse("새게임")

    assert command.type == CommandType.NEW_TOURNAMENT
    assert command.amount == 0


def test_parse_overall_ranking():
    command = parser.parse("전체랭킹")

    assert command.type == CommandType.OVERALL_RANKING
    assert command.amount == 0


def test_parse_force_reset():
    command = parser.parse("@FSS 강제리셋")

    assert command.type == CommandType.FORCE_RESET
    assert command.amount == 0
