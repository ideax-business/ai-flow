<!-- Licensed to the Apache Software Foundation (ASF) under one or more
contributor license agreements.  See the NOTICE file distributed with
this work for additional information regarding copyright ownership.
The ASF licenses this file to You under the Apache License, Version 2.0
(the "License"); you may not use this file except in compliance with
the License.  You may obtain a copy of the License at
  http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License. -->

<template>
  <page-header-wrapper>
    <a-card :bordered="false">
      <div class="table-page-search-wrapper">
        <a-form layout="inline">
          <a-row :gutter="48">
            <a-col :md="8" :sm="24">
              <a-form-item :label="$t('model.label.model_name')">
                <a-input v-model="queryParam.model_name" placeholder=""/>
              </a-form-item>
            </a-col>
            <a-col :md="!advanced && 8 || 24" :sm="24">
              <span class="table-page-search-submitButtons" :style="advanced && { float: 'right', overflow: 'hidden' } || {} ">
                <a-button type="primary" @click="$refs.table.refresh(true)">{{$t('model.button.query')}}</a-button>
                <a-button style="margin-left: 8px" @click="() => this.queryParam = {}">{{$t('model.button.reset')}}</a-button>
              </span>
            </a-col>
          </a-row>
        </a-form>
      </div>
      <s-table
        ref="table"
        size="default"
        rowKey="key"
        :columns="columns"
        :data="loadData"
        showPagination="auto"
      />
    </a-card>
    <a-card :bordered="false">
      <span>Version: <a :href="'https://pypi.org/project/ai-flow/'+version" target="_blank">{{ version }}</a></span>
    </a-card>
  </page-header-wrapper>
</template>

<script>
import moment from 'moment'
import { i18nRender } from '@/locales'
import { STable, Ellipsis } from '@/components'
import { getModels, getVersion } from '@/api/manage'

const columns = [
  {
    title: i18nRender('model.columns.model_name'),
    dataIndex: 'model_name',
    sorter: true
  },
  {
    title: i18nRender('model.columns.model_desc'),
    dataIndex: 'model_desc'
  }
]

export default {
  name: 'Model',
  components: {
    STable,
    Ellipsis
  },
  data () {
    this.columns = columns
    return {
      confirmLoading: false,
      advanced: false,
      queryParam: {},
      loadData: parameter => {
        const requestParameters = Object.assign({}, parameter, this.queryParam)
        console.log('loadData request parameters:', requestParameters)
        return getModels(requestParameters)
          .then(res => {
            console.log(res)
            return res
          })
      },
      version: ''
    }
  },
  mounted () {
    this.getAIFlowVersion()
  },
  methods: {
    resetSearchForm () {
      this.queryParam = {
        date: moment(new Date())
      }
    },
    getAIFlowVersion () {
      getVersion()
        .then(res => {
          this.version = res
        })
    }
  }
}
</script>
