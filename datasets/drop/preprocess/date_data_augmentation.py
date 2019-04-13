from typing import List, Dict, Tuple
import json
import copy
import string
from collections import defaultdict
import datasets.drop.constants as constants
import random
import argparse

random.seed(100)

IGNORED_TOKENS = {'a', 'an', 'the'}
STRIPPED_CHARACTERS = string.punctuation + ''.join([u"‘", u"’", u"´", u"`", "_"])

""" This script is used to augment date-comparison-data by flipping events in the questions """

FIRST = "first"
SECOND = "second"

FIRST_operator_tokens = ['first', 'earlier']
SECOND_operator_tokens = ['later', 'last', 'second']


def readDataset(input_json):
    with open(input_json, 'r') as f:
        dataset = json.load(f)
    return dataset

def find_valid_spans(passage_tokens: List[str],
                     answer_texts: List[str]) -> List[Tuple[int, int]]:

    # debug = False
    # if 'T. J. Houshmandzadeh' in answer_texts:
    #     debug = True
    normalized_tokens = [token.lower().strip(STRIPPED_CHARACTERS) for token in passage_tokens]
    # if debug:
    #     print('\n')
    #     print(normalized_tokens)
    #     print()

    word_positions: Dict[str, List[int]] = defaultdict(list)
    for i, token in enumerate(normalized_tokens):
        word_positions[token].append(i)
    spans = []
    for answer_text in answer_texts:
        # answer_tokens = answer_text.lower().strip(STRIPPED_CHARACTERS).split()
        answer_text_tokens = answer_text.split()
        answer_tokens = [token.lower().strip(STRIPPED_CHARACTERS) for token in answer_text_tokens]
        # if debug:
        #     print(answer_tokens)

        num_answer_tokens = len(answer_tokens)
        if answer_tokens[0] not in word_positions:
            continue


        for span_start in word_positions[answer_tokens[0]]:
            span_end = span_start  # span_end is _inclusive_
            answer_index = 1
            while answer_index < num_answer_tokens and span_end + 1 < len(normalized_tokens):
                token = normalized_tokens[span_end + 1]
                if answer_tokens[answer_index].strip(STRIPPED_CHARACTERS) == token:
                    answer_index += 1
                    span_end += 1
                elif token in IGNORED_TOKENS:
                    span_end += 1
                else:
                    break
            if num_answer_tokens == answer_index:
                spans.append((span_start, span_end))
    return spans


def get_answer_event_order(ans_tokens: List[str], event1_tokens: List[str], event2_tokens: List[str]) -> str:
    event1, event2 = set(event1_tokens), set(event2_tokens)
    ans_event = FIRST if len(event1.intersection(ans_tokens)) > len(event2.intersection(ans_tokens)) else SECOND
    return ans_event


def getQuestionComparisonOperator(question: str) -> str:
    question_tokens = question.split(' ')
    # Correct if Attn1 is first event

    for t in ['first', 'earlier', 'forst', 'firts']:
        if t in question_tokens:
            return FIRST

    for t in ['later', 'last', 'second']:
        if t in question_tokens:
            return SECOND

    return SECOND


def quesEvents(qstr):
    """ Returns (start, end) span tuples for event1 and event2 in the question """
    or_split = qstr.split(' or ')
    if len(or_split) != 2:
        return None

    tokens = qstr.split(' ')

    or_idx = tokens.index('or')
    # Last token is ? which we don't want to attend to
    event2 = tokens[or_idx + 1 : len(tokens) - 1]
    event2_span = (or_idx + 1, len(tokens) - 1)

    # Gets first index of the item
    try:
        comma_idx = tokens.index(',')
    except:
        comma_idx = 100000
    try:
        colon_idx = tokens.index(':')
    except:
        colon_idx = 100000

    try:
        hyphen_idx = tokens.index('-')
    except:
        hyphen_idx = 100000

    split_idx = min(comma_idx, colon_idx, hyphen_idx)

    if split_idx == 100000 or (or_idx - split_idx <= 1):
        # print(f"{qstr} first_split:{split_idx} or:{or_idx}")
        if 'first' in tokens:
            split_idx = tokens.index('first')
        elif 'second' in tokens:
            split_idx = tokens.index('second')
        elif 'last' in tokens:
            split_idx = tokens.index('last')
        elif 'later' in tokens:
            split_idx = tokens.index('later')
        else:
            split_idx = -1

    assert split_idx != -1, f"{qstr} {split_idx} {or_idx}"

    if tokens[or_idx - 1] == ",":
        event1 = tokens[split_idx + 1: or_idx - 1]
        event1_span = (split_idx + 1, or_idx - 1)
    else:
        event1 = tokens[split_idx + 1: or_idx]
        event1_span = (split_idx + 1, or_idx)

    return event1_span, event2_span


def getEventOrderSwitchQuestion(question_answer):
    question_tokenized_text = question_answer[constants.question]
    event_spans = quesEvents(question_tokenized_text)
    if event_spans is None:
        return None
    # These span ends are exclusive
    event1_span, event2_span = event_spans

    new_question_answer = copy.deepcopy(question_answer)

    tokens = question_tokenized_text.split(' ')
    pretext = tokens[0: event1_span[0]]
    event2_text = tokens[event2_span[0]: event2_span[1]]
    mid_text = tokens[event1_span[1]: event2_span[0]]
    event1_text = tokens[event1_span[0]: event1_span[1]]
    end_text = tokens[event2_span[1]:]

    new_question_tokens = pretext + event2_text + mid_text + event1_text + end_text
    new_question_text = ' '.join(new_question_tokens)

    new_question_answer[constants.question] = new_question_text
    # Since we don't know the following, we will keep them blank
    new_question_answer[constants.original_question] = new_question_text
    new_question_answer[constants.answer_question_spans] = []
    # Reversing the order of the date groundings
    qevent_date_groundings = question_answer[constants.datecomp_ques_event_date_groundings]
    qevent_date_values = question_answer[constants.datecomp_ques_event_date_values]
    new_qevent_date_groundings = (qevent_date_groundings[1], qevent_date_groundings[0])
    new_qevent_date_values = (qevent_date_values[1], qevent_date_values[0])
    new_question_answer[constants.datecomp_ques_event_date_groundings] = new_qevent_date_groundings
    new_question_answer[constants.datecomp_ques_event_date_values] = new_qevent_date_values

    new_question_answer["augmented_data"] = True

    return new_question_answer


def getQuestionOperatorSwitchQA(question_answer,
                                passage_tokenized_text, passage_token_charidxs,
                                original_passage_text):
    """ event1_span and event2_span are end-exclusive """

    new_question_answer = copy.deepcopy(question_answer)

    question_tokenized_text = question_answer[constants.question]

    event_spans = quesEvents(question_answer[constants.question])
    if event_spans is None:
        return None
    event1_span, event2_span = event_spans

    question_tokens = question_tokenized_text.split(' ')
    passage_tokens = passage_tokenized_text.split(' ')

    # Get correct answer to find which event in question is correct
    answer_as_passage_spans = question_answer[constants.answer_passage_spans]
    if answer_as_passage_spans:
        passage_ans_span = answer_as_passage_spans[0]
        answer_tokens = passage_tokens[passage_ans_span[0]: passage_ans_span[1] + 1]
    else:
        answer_text = new_question_answer[constants.answer]["spans"][0]
        answer_tokens = answer_text.split(' ')

    event1_tokens = question_tokens[event1_span[0]:event1_span[1]]
    event2_tokens = question_tokens[event2_span[0]:event2_span[1]]
    # First or Second
    answer_event = get_answer_event_order(answer_tokens, event1_tokens, event2_tokens)

    # If event1 of question is original_answer, then the other is the answer for our new question
    if answer_event == FIRST:
        new_ans_tokens = event2_tokens
    else:
        new_ans_tokens = event1_tokens

    if new_ans_tokens[0] == "the":
        new_ans_tokens = new_ans_tokens[1:]

    # Find this question answer span in the passage
    new_ans_as_passage_spans = find_valid_spans(passage_tokens, [' '.join(new_ans_tokens)])
    if not new_ans_as_passage_spans:
        # print(question_tokenized_text)
        # print(new_question_answer[constants.answer]["spans"])
        # print(' '.join(new_ans_tokens))
        # print(' '.join(passage_tokens))
        # print()
        return None

    # Only consider the first grounding
    new_ans_as_passage_span = new_ans_as_passage_spans[0]
    # To find the un-tokenized surface of this answer
    new_ans_start_char_offset, new_ans_end_charoffset = (passage_token_charidxs[new_ans_as_passage_span[0]],
                                                         passage_token_charidxs[new_ans_as_passage_span[1] + 1])

    answer_passage_text = original_passage_text[new_ans_start_char_offset:new_ans_end_charoffset]

    new_question_answer[constants.answer]["spans"] = [answer_passage_text]
    new_question_answer[constants.answer_question_spans] = []
    new_question_answer[constants.answer_passage_spans] = [new_ans_as_passage_span]

    # Make the new question -
    original_ques_operator = getQuestionComparisonOperator(question_tokenized_text)
    # not using the FIRST_operator_tokens list since there is noise in original question
    if original_ques_operator == FIRST:
        tokens_to_replace = ['first', 'earlier', 'forst', 'firts']
        new_operator_token = random.choice(SECOND_operator_tokens)
    else:
        tokens_to_replace = ['later', 'last', 'second']
        new_operator_token = random.choice(FIRST_operator_tokens)

    # Replace the
    new_question_text = question_tokenized_text
    for t in tokens_to_replace:
        new_question_text = new_question_text.replace(t, new_operator_token)

    # Original question doesn't contain first, last kind replacable words. Hence skipping
    if question_tokenized_text == new_question_text:
        return None

    new_question_answer[constants.question] = new_question_text
    new_question_answer[constants.original_question] = new_question_text

    new_question_answer["augmented_data"] = True

    return new_question_answer


def getFlippedQuestions(dataset):
    new_dataset = {}
    original_operator_dist = defaultdict(float)
    augment_operator_dist = defaultdict(float)

    num_qa_original = 0
    num_qa_augment = 0

    for passage_id, passage_info in dataset.items():
        new_qa_pairs = []
        passage_tokenized_text = passage_info[constants.passage]
        passage_token_charidxs = passage_info[constants.passage_charidxs]
        original_passage_text = passage_info[constants.original_passage]
        num_qa_original += len(passage_info[constants.qa_pairs])
        for question_answer in passage_info[constants.qa_pairs]:
            question_tokenized_text = question_answer[constants.question]
            ques_operator = getQuestionComparisonOperator(question_tokenized_text)
            original_operator_dist[ques_operator] += 1

            new_qa_pairs.append(question_answer)
            augment_operator_dist[ques_operator] += 1

            # "first A or B" --> "first B or A"
            event_switch_question_answer = getEventOrderSwitchQuestion(question_answer)
            if event_switch_question_answer is not None:
                new_qa_pairs.append(event_switch_question_answer)
                ques_operator = getQuestionComparisonOperator(event_switch_question_answer[constants.question])
                augment_operator_dist[ques_operator] += 1

            # "first A or B" --> "second A or B"
            qoperator_switch_question_answer = getQuestionOperatorSwitchQA(question_answer,
                                                                           passage_tokenized_text,
                                                                           passage_token_charidxs,
                                                                           original_passage_text)

            if qoperator_switch_question_answer is not None:
                ques_operator = getQuestionComparisonOperator(qoperator_switch_question_answer[constants.question])
                augment_operator_dist[ques_operator] += 1
                new_qa_pairs.append(qoperator_switch_question_answer)

            # "first B or A" --> "second B or A"
            event_sw_qoperator_sw_question_answer = getQuestionOperatorSwitchQA(event_switch_question_answer,
                                                                                passage_tokenized_text,
                                                                                passage_token_charidxs,
                                                                                original_passage_text)
            if event_sw_qoperator_sw_question_answer is not None:
                ques_operator = getQuestionComparisonOperator(event_sw_qoperator_sw_question_answer[constants.question])
                augment_operator_dist[ques_operator] += 1
                new_qa_pairs.append(event_switch_question_answer)

        num_qa_augment += len(new_qa_pairs)
        passage_info[constants.qa_pairs] = new_qa_pairs
        new_dataset[passage_id] = passage_info
    print()
    print(f"Num of original question: {num_qa_original}")
    print(original_operator_dist)
    print(f"Num of original question: {num_qa_augment}")
    print(augment_operator_dist)

    return new_dataset


if __name__=='__main__':
    # input_dir = "date_prune_weakdate"
    # trnfp = f"/srv/local/data/nitishg/data/drop/{input_dir}/drop_dataset_train.json"
    # devfp = f"/srv/local/data/nitishg/data/drop/{input_dir}/drop_dataset_dev.json"
    #
    # output_dir = "date_prune_weakdate_augment"
    # out_trfp = f"/srv/local/data/nitishg/data/drop/{output_dir}/drop_dataset_train.json"
    # out_devfp = f"/srv/local/data/nitishg/data/drop/{output_dir}/drop_dataset_dev.json"
    print("Running data augmentation")

    parser = argparse.ArgumentParser()
    parser.add_argument('--input_trnfp')
    parser.add_argument('--input_devfp')
    parser.add_argument('--output_trnfp')
    parser.add_argument('--output_devfp')
    parser.add_argument('--no_weakdate', action='store_true', default=False)
    args = parser.parse_args()

    weakdate = not args.no_weakdate

    input_trnfp = args.input_trnfp
    input_devfp = args.input_devfp
    output_trnfp = args.output_trnfp
    output_devfp = args.output_devfp

    train_dataset = readDataset(input_trnfp)
    dev_dataset = readDataset(input_devfp)

    new_train_dataset = getFlippedQuestions(train_dataset)
    new_dev_dataset = getFlippedQuestions(dev_dataset)

    with open(output_trnfp, 'w') as f:
        json.dump(new_train_dataset, f, indent=4)

    with open(output_devfp, 'w') as f:
        json.dump(new_dev_dataset, f, indent=4)


    print("Written augmented datasets")
