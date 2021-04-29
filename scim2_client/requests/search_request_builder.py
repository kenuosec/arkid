#!/usr/bin/env python3
import requests
from urllib.parse import urljoin
from .base_request_builder import BaseRequestBuilder
from scim2_client.constants import (
    QUERY_PARAMETER_FILTER,
    QUERY_PARAMETER_SORT_BY,
    QUERY_PARAMETER_SORT_ORDER,
    QUERY_PARAMETER_PAGE_START_INDEX,
    QUERY_PARAMETER_PAGE_SIZE,
    QUERY_PARAMETER_ATTRIBUTES,
    QUERY_PARAMETER_EXCLUDED_ATTRIBUTES,
    SEARCH_WITH_POST_PATH_EXTENSION,
)


class SearchRequestBuilder(BaseRequestBuilder):
    def __init__(self, endpoint):
        super().__init__(self, endpoint)

    def filter(self, filter_str):
        self.filter_str = filter_str
        return self

    def sort(self, sort_by, sort_order):
        assert sort_order in ['ascending', 'descending']
        self.sort_by = sort_by
        self.sort_order = sort_order
        return self

    def page(self, start_index, count):
        if start_index and count:
            self.start_index = start_index
            self.count = count
        return self

    def build_data(self):
        data = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:SearchRequest"],
            QUERY_PARAMETER_FILTER: self.filter_str,
            QUERY_PARAMETER_SORT_BY: self.sort_by,
            QUERY_PARAMETER_SORT_ORDER: self.sort_order,
            QUERY_PARAMETER_PAGE_START_INDEX: self.start_index,
            QUERY_PARAMETER_PAGE_SIZE: self.count,
        }
        if self.attributes:
            if self.is_excluded:
                data[QUERY_PARAMETER_EXCLUDED_ATTRIBUTES] = ','.join(self.attributes)
            else:
                data[QUERY_PARAMETER_ATTRIBUTE] = ','.join(self.attributes)

    def build_params(self):
        if self.filter_str:
            self.params[QUERY_PARAMETER_FILTER] = filter_str
        if self.sort_by:
            self.params[QUERY_PARAMETER_SORT_BY] = sort_by
        if self.sort_order:
            self.params[QUERY_PARAMETER_SORT_ORDER] = sort_order
        if self.start_index and self.count:
            self.params[QUERY_PARAMETER_PAGE_START_INDEX] = start_index
            self.params[QUERY_PARAMETER_PAGE_SIZE] = count

    def invoke(self, use_post=False):
        if use_post:
            data = self.build_data()
            url = urljoin(self.base_url, SEARCH_WITH_POST_PATH_EXTENSION)
            r = requests.post(url, data=data, headers=self.headers)
            return r.status_code, r.text
        else:
            super().invoke()
            self.build_params()
            r = requests.get(self.base_url, params=self.params, headers=self.headers)
            return r.status_code, r.text
