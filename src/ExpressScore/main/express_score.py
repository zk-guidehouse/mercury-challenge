'''
Module to provide lightweight scoring functions for Mercury Challenge participants to score their warnings as part of their test and development process.
'''

import sys
import re

from .schema import (
    JSONField,
    ScoreComponents,
    EventType,
    Subtype,
    LocationName
)

import datetime
try:
    from ciso8601 import parse_datetime as parse
except ImportError:
    from dateutil.parser import parse
from collections import (
    ChainMap,
    OrderedDict
)

import numpy as np
import pandas as pd
from geopy.distance import distance

import dlib


class Defaults(object):
    """
    Holds default values for scoring system parameters
    """
    ACCURACY_DENOMINATOR = 4
    LS_WEIGHT = 1.0
    DS_WEIGHT = 1.0
    AS_WEIGHT = 1.0
    ESS_WEIGHT = 1.0
    MAX_DIST = 100.0
    DIST_BUFFER = MAX_DIST/6.0
    MAX_DATE_DIFF = 4.0
    DATE_BUFFER = 4.0
    MAX_DATE_PERIOD = 50


class Scorer:
    '''
    Base class for all scoring classes.
    '''


    def __init__(self):
        pass

    def score(self, warn_data, gsr_data):
        '''
        Scores the warning data against the GSR data.
        :param warn_data: List of dicts of warnings
        :param gsr_data: List of dicts of GSR events
        :return: Dict of scoring results
        '''
        match_ = self.match(warn_data, gsr_data)
        out_dict = dict()
        return out_dict

    def score_one(self, warn_, event_):
        """
        Scores a single warning against a single GSR event
        :param warn_: dict with data for a warning.
        :param event_: dict with data for a GSR event
        :return: dict with scoring results
        """
        out_dict = dict()
        return out_dict()

    @staticmethod
    def match(input_matrix, allow_zero_scores=False):
        """
        Matches the warnings to the GSR events
        :param warn_data: List of dicts of warnings
        :param gsr_data: Lists of dicts of GSR events.
        :return: List of matched data
        """
        return []

    @staticmethod
    def slope_score(result, min_value, max_value):
        """
        Provides a score for the result scaled to 0 to 1
        :param result: Value to be scored
        :param min_value: Smallest allowable value
        :param max_value: Largest allowable value
        :return: Score from 0.0 to 1.0
        """
        if min_value == max_value:
            raise ValueError("Minimum and maximum thresholds must be different")
        if min_value > max_value:
            raise ValueError("Minimum threshold must be less than maximum threshold")

        slope = max_value - min_value
        result = min(result, max_value)
        result = max(result, min_value)
        score = 1 - (result - min_value)/slope

        return score

    @staticmethod
    def facet_score(warn_value, gsr_value, wildcards=[]):
        """
        Sees if warning and GSR match
        :param warn_value: Value from the warning
        :param gsr_value: Value from the event
        :param wildcards: A list of GSR values that match any warning value.
        :return: 1 if they match, 0 otherwise.
        """
        if isinstance(gsr_value, (list, tuple)):
            pass
        else:
            gsr_value = [gsr_value]

        if len(set(wildcards).intersection(set(gsr_value))) > 0:
            matched_value = 1
        else:
             matched_value = int(warn_value in gsr_value)

        return matched_value

    @staticmethod
    def f1(precision, recall):
        """
        Computes F1 metric
        :param precision: Precision
        :param recall: Recall
        :return: Harmonic mean of Precision and Recall
        """
        if (precision < 0) or (precision > 1):
            raise ValueError("Precision must be in the range 0.0 to 1.0")
        if (recall < 0) or (recall > 1):
            raise ValueError("Recall must be in the range 0.0 to 1.0")
        if precision == recall == 0:
            f1_out = 0
        else:
            f1_out = 2*precision*recall/(precision+recall)
        return f1_out

    @staticmethod
    def make_combination_mats(row_value_list, column_value_list):
        """
        Creates dual index matrices for use in other computations.  The warning index matrix will
        have one row per warning index element, the GSR index matrix will have one column per GSR index element.
        :return: pair of matrices
        """
        n_row = len(row_value_list)
        n_col = len(column_value_list)
        row_value_array = np.array(n_col * list(row_value_list))
        row_value_array = row_value_array.reshape(n_col, n_row)
        row_value_array = row_value_array.T
        column_value_array = np.array(n_row * list(column_value_list))
        column_value_array = column_value_array.reshape(n_row, n_col)

        return row_value_array, column_value_array

    @staticmethod
    def make_index_mats(row_value_list, column_value_list):
        """
        Creates dual index matrices for use in other computations.  The warning index matrix will
        have one row per warning index element, the GSR index matrix will have one column per GSR index element.
        :return: pair of matrices
        """
        n_row = len(row_value_list)
        n_col = len(column_value_list)
        row_value_i_list = list(range(n_row))
        row_value_i_array = np.array(n_col * row_value_i_list)
        row_value_i_array = row_value_i_array.reshape(n_col, n_row)
        row_value_i_array = row_value_i_array.T
        column_value_i_list = list(range(n_col))
        column_value_i_array = np.array(n_row * column_value_i_list)
        column_value_i_array = column_value_i_array.reshape(n_row, n_col)

        return row_value_i_array, column_value_i_array

    @staticmethod
    def date_diff(warn_date, gsr_date):
        """
        Computes date difference based on warning date and event date.
        :param warn_date: Event_Date in the warning
        :param gsr_date: Event_Date in the GSR
        :return: integer, negative values mean the warning was later than the event
        """
        gsr_d = parse(gsr_date).date()
        warn_d = parse(warn_date).date()
        date_diff = (gsr_d - warn_d).days
        return date_diff

    @staticmethod
    def date_score(date_diff, max_diff=Defaults.MAX_DATE_DIFF):
        """Computes the date score between date1 and date2, with
        a date_diff of max_diff scoring 0
        :param max_diff: Maximum allowable time difference
        :param date_diff: Number of days between actual and warning event dates
        :return: Float
        """

        date_diff = np.abs(date_diff)
        score = Scorer.slope_score(date_diff, 0, max_diff)
        return score


class CaseCountScorer(Scorer):
    """
    Scores the case count event types
    """
    LOCATIONS = [LocationName.EGYPT, LocationName.JORDAN, LocationName.SAUDI_ARABIA,
                 LocationName.TAHRIR, LocationName.AMMAN, LocationName.IRBID, LocationName.MADABA]
    LOCATION_DICT = dict()
    LOCATION_DICT[LocationName.EGYPT] = {JSONField.COUNTRY: LocationName.EGYPT}
    LOCATION_DICT[LocationName.SAUDI_ARABIA] = {JSONField.COUNTRY: LocationName.SAUDI_ARABIA}
    LOCATION_DICT[LocationName.JORDAN] = {JSONField.COUNTRY: LocationName.JORDAN}
    LOCATION_DICT[LocationName.TAHRIR] = {JSONField.COUNTRY: LocationName.EGYPT,
                                          JSONField.CITY: LocationName.TAHRIR}
    LOCATION_DICT[LocationName.AMMAN] = {JSONField.COUNTRY: LocationName.JORDAN,
                                         JSONField.STATE: LocationName.AMMAN}
    LOCATION_DICT[LocationName.IRBID] = {JSONField.COUNTRY: LocationName.JORDAN,
                                         JSONField.STATE: LocationName.IRBID}
    LOCATION_DICT[LocationName.MADABA] = {JSONField.COUNTRY: LocationName.JORDAN,
                                          JSONField.STATE: LocationName.MADABA}


    def __init__(self, event_type, location):
        """
        Sets the event type
        :param event_type: Event_Type value
        :param location: The location being scored
        """
        details = CaseCountScorer.fill_out_location(event_type=event_type, location=location)
        self.event_type = details[JSONField.EVENT_TYPE]
        if JSONField.COUNTRY in details:
            self.country = details[JSONField.COUNTRY]
        else:
            self.country = None
        if JSONField.STATE in details:
            self.state = details[JSONField.STATE]
        else:
            self.state = None
        if JSONField.CITY in details:
            self.city = details[JSONField.CITY]
        else:
            self.city = None

    @staticmethod
    def fill_out_location(location, event_type):
        """
        Completes the location specification
        :param location: Location input
        :param event_type: Event Type
        :return: dict with location parameters
        """
        out_dict = {JSONField.EVENT_TYPE: event_type}
        if location in CaseCountScorer.LOCATIONS:
            loc_dict = CaseCountScorer.LOCATION_DICT[location]
            for k in loc_dict:
                out_dict[k] = loc_dict[k]

        return out_dict

    @staticmethod
    def score_one(warn_, event_, accuracy_denominator=Defaults.ACCURACY_DENOMINATOR):
        """
        Scores a single warning against a single GSR event
        :param warn_: dict with warning data
        :param event_: dict with event data
        :param accuracy_denominator: Threshold for scaling with small case counts
        :return: dict with scoring results
        """
        predicted = warn_[JSONField.CASE_COUNT]
        actual = event_[JSONField.CASE_COUNT]
        qs = CaseCountScorer.quality_score(predicted, actual, accuracy_denominator)
        out_dict = dict()
        out_dict[JSONField.WARNING_ID] = warn_[JSONField.WARNING_ID]
        out_dict[JSONField.EVENT_ID] = event_[JSONField.EVENT_ID]
        out_dict[JSONField.WARN_VALUE] = predicted
        out_dict[JSONField.EVENT_VALUE] = actual
        out_dict[ScoreComponents.QS] = qs
        return out_dict

    @staticmethod
    def quality_score(predicted, actual, accuracy_denominator=Defaults.ACCURACY_DENOMINATOR):
        """
        Computes quality score on a scale of 0.0 to 1.0
        :param predicted: The predicted value
        :param actual: The actual value
        :param accuracy_denominator: The minimum value for scaling differences
        :return: Quality score value
        """
        if predicted <0 or actual<0:
            print("Negative case counts are not allowed")
            return
        if accuracy_denominator <= 0:
            print("The accuracy denominator must be positive.")
            return
        numerator = abs(predicted-actual)
        denominator = max(predicted, actual, accuracy_denominator)
        qs = 1 - 1.*numerator/denominator
        return qs

    def make_score_df(self, warn_data, gsr_data):
        """
        Matches Warning to GSR by event date
        :param warn_data:
        :param gsr_data:
        :return: DataFrame with merged data
        """
        warn_df = pd.DataFrame(warn_data)
        warn_df = warn_df[warn_df[JSONField.EVENT_TYPE] == self.event_type]
        warn_df = warn_df[warn_df[JSONField.COUNTRY] == self.country]
        if self.state is not None:
            warn_df = warn_df[warn_df[JSONField.STATE] == self.state]
        if self.city is not None:
            warn_df = warn_df[warn_df[JSONField.CITY] == self.city]
        gsr_df = pd.DataFrame(gsr_data)
        gsr_df = gsr_df[gsr_df[JSONField.EVENT_TYPE] == self.event_type]
        gsr_df = gsr_df[gsr_df[JSONField.COUNTRY] == self.country]
        if self.state is not None:
            gsr_df = gsr_df[gsr_df[JSONField.STATE] == self.state]
        if self.city is not None:
            gsr_df = gsr_df[gsr_df[JSONField.CITY] == self.city]
        score_df = pd.merge(left=warn_df, right=gsr_df, on=JSONField.EVENT_DATE, how="outer")
        score_df["Warning_Case_Count"] = score_df.Case_Count_x
        score_df["GSR_Case_Count"] = score_df.Case_Count_y
        drop_cols = [c for c in score_df.columns if re.findall("_x|_y", c)]
        for c in drop_cols:
            score_df.drop(c, axis=1, inplace=True)
        return score_df

    def match(self, warn_data, gsr_data):
        """
        Matches Warning to GSR by event date
        :param warn_data:
        :param gsr_data:
        :return:
        """
        score_df = self.make_score_df(warn_data, gsr_data)
        out_dict = dict()
        unmatched_warn_df = score_df[score_df[JSONField.EVENT_ID].isnull()]
        unmatched_warn_list = list(unmatched_warn_df[JSONField.WARNING_ID].values)
        out_dict["Unmatched Warnings"] = unmatched_warn_list
        unmatched_gsr_df = score_df[score_df[JSONField.WARNING_ID].isnull()]
        unmatched_gsr_list = list(unmatched_gsr_df[JSONField.EVENT_ID].values)
        out_dict["Unmatched GSR"] = unmatched_gsr_list
        matched_df = score_df[~score_df[JSONField.EVENT_ID].isnull()]
        matched_df = matched_df[~matched_df[JSONField.WARNING_ID].isnull()]
        match_list = list(zip(matched_df[JSONField.WARNING_ID].values,
                         matched_df[JSONField.EVENT_ID].values))
        out_dict["Matches"] = match_list
        return out_dict

    def score(self, warn_data, gsr_data):
        """
        Perform scoring on Case Count event types
        :param warn_data: List of dicts of warnings
        :param gsr_data: List of dicts of GSR events
        :return: Dict with scoring results.
        """
        score_df = self.make_score_df(warn_data, gsr_data)
        matches = self.match(warn_data, gsr_data)
        out_dict = matches.copy()
        scorable_df = score_df[~score_df.Warning_ID.isnull()]
        scorable_df = scorable_df[~scorable_df.Event_ID.isnull()]
        qs_ser = scorable_df.apply(lambda x: CaseCountScorer.quality_score(x.Warning_Case_Count,
                                                                           x.GSR_Case_Count),
                                                      axis=1)
        mean_qs = qs_ser.mean()
        result_dict = dict()
        result_dict[ScoreComponents.QS] = mean_qs
        n_warn = len(score_df[~score_df.Warning_ID.isnull()])
        n_gsr = len(score_df[~score_df.Event_ID.isnull()])
        n_match = len(scorable_df)
        precision = n_match/n_warn
        recall = n_match/n_gsr
        result_dict["Precision"] = precision
        result_dict["Recall"] = recall
        out_dict["Results"] = result_dict
        qs_values = list(qs_ser.values)
        details_dict = dict()
        details_dict["QS Values"] = qs_values
        out_dict["Details"] = details_dict

        return out_dict


class MaScorer(Scorer):
    """
    Scorer for Military Action events
    """

    STATE_ACTORS = ["Fred", "Ethel"]
    WILDCARD_ACTORS = ["Unspecified"]
    ACTORS = STATE_ACTORS + WILDCARD_ACTORS
    SUBTYPES = [Subtype.CONFLICT, Subtype.FORCE_POSTURE]

    # Precompute all possible date differences
    warn_dates = np.array(range(Defaults.MAX_DATE_PERIOD))
    gsr_dates = np.array(range(Defaults.MAX_DATE_PERIOD))
    dd_index_mats = Scorer.make_index_mats(warn_dates, gsr_dates)
    all_dd_mat = dd_index_mats[0] - dd_index_mats[1]
    ds_vfunc = np.vectorize(Scorer.date_score)

    def __init__(self, country):
        """
        :param country: The country to be scored
        """
        self.event_type = EventType.MA
        self.country = country

    @staticmethod
    def match(input_matrix, allow_zero_scores=False):
        """
        Builds match list
        :param input_matrix: 2 dimensional array of scores
        :param allow_zero_scores: Should items with a score of 0 be considered to be matched?  Default is False
        :return:
        """
        out_dict = dict()
        out_dict["Matches"] = []
        out_dict["Details"] = {"Quality Scores": []}
        out_dict["Quality Score"] = 0
        out_dict["Precision"] = 0
        out_dict["Recall"] = 0
        out_dict["F1"] = 0
        warn_id_list = list(input_matrix.index)
        event_id_list = list(input_matrix.columns)
        score_matrix = np.array(input_matrix)

        if min(score_matrix.shape) == 0:
            pass
        else:
            if np.max(score_matrix) <= 0:
                pass
            else:
                score_matrix = score_matrix.copy(order="C")
                row_count, col_count = score_matrix.shape
                zero_matrix = np.zeros(score_matrix.shape)
                score_matrix = np.maximum(score_matrix, zero_matrix)

                k_max = max(score_matrix.shape[0], score_matrix.shape[1])
                score_matrix_square = np.zeros((k_max, k_max))
                score_matrix_square[:score_matrix.shape[0], :score_matrix.shape[1]] = score_matrix

                assign = dlib.max_cost_assignment(dlib.matrix(score_matrix_square))
                assign = [(i, assign[i]) for i in range(k_max)]

                assign_scores = np.array([score_matrix_square[x[0], x[1]] for x in assign])
                assign = np.array(assign)

                #assign = assign[assign_scores > 0]

                if not allow_zero_scores:
                    assign_scores = np.array([score_matrix_square[x[0], x[1]] for x in assign])
                    assign = np.array(assign)
                    assign = assign[assign_scores > 0]
                assign = list([tuple(x) for x in assign])
                assign = [(int(x[0]), int(x[1])) for x in assign]
                assign = [(warn_id_list[a[0]], event_id_list[a[1]]) for a in assign]
                out_dict["Matches"] = assign
                scores_ = assign_scores[assign_scores > 0]
                out_dict["Quality Score"] = np.mean(scores_)
                out_dict["Details"] = {"Quality Scores": list(scores_)}
                prec = len(assign)/row_count
                rec = len(assign)/col_count
                out_dict["Precision"] = prec
                out_dict["Recall"] = rec
                out_dict["F1"] = Scorer.f1(prec, rec)

        return out_dict

    @staticmethod
    def score_one(warn_, event_, max_dist=Defaults.MAX_DIST, dist_buffer=Defaults.DIST_BUFFER,
                  max_date_diff=Defaults.MAX_DATE_DIFF, legit_actors=ACTORS, wildcards=WILDCARD_ACTORS,
                  ls_weight=Defaults.LS_WEIGHT, ds_weight=Defaults.DS_WEIGHT, as_weight=Defaults.AS_WEIGHT,
                  ess_weight = Defaults.ESS_WEIGHT):
        """
        Scores a single warning against a single event
        :param warn_: Dict with data for a warning
        :param event_: Dict with data for an event
        :return: Dict with scoring details
        """
        bad_qs = False
        error_list = []
        notice_list = []
        if ls_weight < 0:
            bad_qs = True
            error_list.append("LS Weight must be positive")
        if ds_weight < 0:
            bad_qs = True
            error_list.append("DS Weight must be positive")
        if as_weight < 0:
            bad_qs = True
            error_list.append("AS Weight must be positive")
        if ess_weight < 0:
            bad_qs = True
            error_list.append("ESS Weight must be positive")
        weight_sum = ls_weight + ds_weight + as_weight + ess_weight
        if weight_sum != 4.0:
            notice_list.append("Reweighting so that sum of weights is 4.0")
            ls_weight = 4*ls_weight/weight_sum
            ds_weight = 4*ds_weight/weight_sum
            as_weight = 4*as_weight/weight_sum
            ess_weight = 4*ess_weight/weight_sum

        out_dict = dict()
        # Compute the distance
        out_dict[JSONField.WARNING_ID] = warn_[JSONField.WARNING_ID]
        out_dict[JSONField.EVENT_ID] = event_[JSONField.EVENT_ID]
        if error_list:
            out_dict["Errors"] = error_list
        else:
            warn_lat = warn_[JSONField.LATITUDE]
            warn_long = warn_[JSONField.LONGITUDE]
            event_lat = event_[JSONField.LATITUDE]
            event_long = event_[JSONField.LONGITUDE]
            loc_approx = event_[JSONField.APPROXIMATE_LOCATION]
            out_dict[JSONField.APPROXIMATE_LOCATION] = loc_approx
            dist = distance((warn_lat, warn_long), (event_lat, event_long)).km
            out_dict["Distance"] = dist
            warn_event_date = warn_[JSONField.EVENT_DATE]
            event_event_date = event_[JSONField.EVENT_DATE]
            gsr_d = parse(event_event_date).date()
            warn_d = parse(warn_event_date).date()
            date_diff = (gsr_d - warn_d).days
            date_diff = np.abs(date_diff)
            out_dict["Date Difference"] = date_diff
            ls = MaScorer.location_score(warn_lat, warn_long, event_lat, event_long, loc_approx, max_dist, dist_buffer)
            out_dict[ScoreComponents.LS] = ls
            date_delta = Scorer.date_diff(warn_event_date, event_event_date)
            ds = Scorer.date_score(date_delta, max_date_diff)
            out_dict[ScoreComponents.DS] = ds
            # Event Subtype
            warn_es = warn_[JSONField.SUBTYPE]
            gsr_es = event_[JSONField.SUBTYPE]
            ess = MaScorer.event_subtype_score(warn_es, gsr_es)
            out_dict[ScoreComponents.ESS] = ess
            # Actor Score
            warn_actor = warn_[JSONField.ACTOR]
            event_actor = event_[JSONField.ACTOR]
            _as = MaScorer.actor_score(warn_actor, event_actor, legit_actors, wildcards)
            out_dict[ScoreComponents.AS] = _as
            if min(ls, ds) == 0:
                qs = 0
            else:
                qs = ls_weight*ls + ds_weight*ds + as_weight*_as + ess_weight*ess
            out_dict[ScoreComponents.QS] = qs
        # Quality Score
        if notice_list:
            out_dict["Notices"] = notice_list
        return out_dict

    def score(self, warn_data, gsr_data):
        """
        Scores the warnings against the GSR
        :param warn_data: List of dicts with warning data
        :param gsr_data: List of dicts with event data
        :return: dict with scoring results
        """

        out_dict = dict()

        return out_dict

    @staticmethod
    def location_score(lat1, long1, lat2, long2, is_approximate=False,
                       max_dist=Defaults.MAX_DIST, dist_buffer=Defaults.DIST_BUFFER):
        """
        Computes location score based on the distance provided.
        :param lat1: Latitude of point 1
        :param long1: Longitude of point 1
        :param lat2: Latitude of point 2
        :param long2: Longitude of point 2
        :param is_approximate: Is the reference location approximate?
        :param max_dist: What is the maximum distance allowed?
        :param dist_buffer: For approximate locations, how much do we give credit for?
        :return: score from 0 to 1.0
        """

        dist_km = distance((lat1, long1), (lat2, long2)).km
        if isinstance(is_approximate, str):
            is_approximate = eval(is_approximate)
        is_approximate = int(is_approximate)
        max_dist = max_dist - is_approximate*dist_buffer
        dist_km = dist_km - is_approximate*dist_buffer
        ls = Scorer.slope_score(dist_km, 0, max_dist)
        return ls

    @staticmethod
    def actor_score(warn_actor, gsr_actor, legit_actors=ACTORS,
                    wildcards=WILDCARD_ACTORS):
        """
        Computes the facet score for Actor
        :param warn_actor: Warning value for Actor
        :param gsr_actor: GSR value for Actor, could be a list
        :param legit_actors: Which actors are legal values for submission
        :param wildcards: Which values in the GSR are assumed to match all legit inputs?
        :return: 1 if it matches, 0 if it doesn't.
        """

        if warn_actor not in legit_actors:
            _as = 0
        else:
            _as = Scorer.facet_score(warn_actor, gsr_actor, wildcards)

        return _as

    @staticmethod
    def event_subtype_score(warn_subtype, gsr_subtype):
        """
        Computes the facet score for Event Subtype
        :param warn_subtype: Warning value for Event Subtype
        :param gsr_subtype: GSR value for Subtype, could be a list
        :return: 1 if it matches, 0 if it doesn't.
        """

        if warn_subtype not in MaScorer.SUBTYPES:
            ess = 0
        else:
            ess = Scorer.facet_score(warn_subtype, gsr_subtype)

        return ess
