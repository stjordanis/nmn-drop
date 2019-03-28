import json
import random
import logging
import itertools
import numpy as np
from typing import Dict, List, Union, Tuple, Any
from collections import defaultdict
from overrides import overrides
from allennlp.common.file_utils import cached_path
from allennlp.data.dataset_readers.dataset_reader import DatasetReader
from allennlp.data.instance import Instance
from allennlp.data.dataset_readers.reading_comprehension.util import make_reading_comprehension_instance
from allennlp.data.token_indexers import SingleIdTokenIndexer, TokenIndexer
from allennlp.data.tokenizers import Token, Tokenizer, WordTokenizer
from allennlp.data.dataset_readers.reading_comprehension.util import IGNORED_TOKENS, STRIPPED_CHARACTERS
from allennlp.data.fields import Field, TextField, MetadataField, LabelField, ListField, \
    SequenceLabelField, SpanField, IndexField, ProductionRuleField, ArrayField

from semqa.domain_languages.drop.drop_language import DropLanguage, Date, get_empty_language_object

from datasets.drop import constants

# from reading_comprehension.utils import split_tokens_by_hyphen

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


# TODO: Add more number here
WORD_NUMBER_MAP = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
                   "five": 5, "six": 6, "seven": 7, "eight": 8,
                   "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
                   "thirteen": 13, "fourteen": 14, "fifteen": 15,
                   "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}


@DatasetReader.register("passage_attn2span_reader")
class DROPReader(DatasetReader):
    def __init__(self,
                 lazy: bool = False,
                 min_passage_length=200,
                 max_passage_length=400,
                 max_span_length=10,
                 num_training_samples=2000,
                 attnval: float = 1.0,
                 normalized=True,
                 withnoise=True)-> None:
        super().__init__(lazy)

        self._min_passage_length = min_passage_length
        self._max_passage_length = max_passage_length
        self._max_span_length = max_span_length
        self._num_training_samples = num_training_samples
        self._normalized = normalized
        self._attnval = attnval
        self._withnoise = withnoise

    @overrides
    def _read(self, file_path: str):
        # pylint: disable=logging-fstring-interpolation
        logger.info(f"Making {self._num_training_samples} training examples with:\n"
                    f"max_passage_length: {self._max_passage_length}\n"
                    f"min_passage_len: {self._min_passage_length}\n"
                    f"max_span_len:{self._max_span_length}\n")

        instances: List[Instance] = []
        for i in range(self._num_training_samples):
            fields: Dict[str, Field] = {}

            passage_length = random.randint(self._min_passage_length, self._max_passage_length)
            attention = [0.0 for _ in range(passage_length)]

            span_length = random.randint(1, self._max_span_length)

            # Inclusive start and end positions
            start_position = random.randint(0, passage_length - span_length)
            end_position = start_position + span_length - 1

            attention[start_position:end_position + 1] = [1.0] * span_length

            if self._withnoise:
                attention = [x + abs(random.gauss(0, 0.001)) for x in attention]

            if self._normalized:
                attention_sum = sum(attention)
                attention = [float(x)/attention_sum for x in attention]

            passage_span_fields = ArrayField(np.array([[start_position, end_position]]), padding_value=-1)

            fields["passage_attention"] = ArrayField(np.array(attention), padding_value=0.0)

            fields["passage_lengths"] = MetadataField(passage_length)

            fields["answer_as_passage_spans"] = passage_span_fields

            instances.append(Instance(fields))

            print("Making data")

        return instances