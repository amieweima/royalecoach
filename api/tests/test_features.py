from datetime import datetime

from conftest import DECK_A, DECK_B, deck_json, make_battle

from app.ml.features import battles_to_frame, card_vocabulary, make_matrix


def test_frame_basic_columns(session):
    session.add_all([make_battle(i, won=i % 2) for i in range(10)])
    session.commit()

    frame = battles_to_frame(session)
    assert len(frame) == 10
    assert frame["won"].tolist() == [i % 2 for i in range(10)]
    assert (frame["trophy_diff"] == 0).all()


def test_mirror_duplicates_dropped(session):
    when = datetime(2026, 8, 15, 12, 0)
    mine = make_battle(0, won=1, p_tag="#AAA", o_tag="#BBB", when=when)
    # Same battle harvested from the opponent's perspective.
    theirs = make_battle(
        0, won=0, p_tag="#BBB", o_tag="#AAA", when=when,
        p_deck=deck_json(DECK_B), o_deck=deck_json(DECK_A),
    )
    session.add_all([mine, theirs])
    session.commit()

    frame = battles_to_frame(session)
    assert len(frame) == 1


def test_underlevel_features(session):
    under = deck_json(DECK_A, level=11, max_level=14)  # 3 below max, all cards
    session.add(make_battle(0, p_deck=under))
    session.commit()

    frame = battles_to_frame(session)
    assert frame.loc[0, "p_underlevel_mean"] == 3
    assert frame.loc[0, "p_underlevel_max"] == 3
    assert frame.loc[0, "o_underlevel_mean"] == 0


def test_vocabulary_filters_rare_cards(session):
    rare_deck = deck_json(["Rare Card"] + DECK_A[:7])
    battles = [make_battle(i) for i in range(99)] + [make_battle(99, p_deck=rare_deck)]
    session.add_all(battles)
    session.commit()

    frame = battles_to_frame(session)
    vocab = card_vocabulary(frame, min_freq=0.05)
    assert "Rare Card" not in vocab
    assert "Hog Rider" in vocab
    assert "Golem" in vocab


def test_matrix_multihot(session):
    session.add_all([make_battle(i) for i in range(5)])
    session.commit()

    frame = battles_to_frame(session)
    vocab = card_vocabulary(frame, min_freq=0.0)
    X, y = make_matrix(frame, vocab)

    assert len(X) == len(y) == 5
    # Every card in the vocab yields one column per side.
    assert X.shape[1] == 6 + 2 * len(vocab)
    assert (X["p::Hog Rider"] == 1).all()
    assert (X["o::Hog Rider"] == 0).all()
    assert (X["o::Golem"] == 1).all()
