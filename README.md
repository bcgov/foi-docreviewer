# FOI Dedupe, Document Extraction ,  NLP Services and related Data, Document Storage

## Introduction
FOI Dedupe, Document extraction and NLP Services described in this documentation will be a value added service(s) on top of current FOI FLOW implementation. These services will support FOI FLOW application for document review, harms assessment and Redaction(PII, Confidentials etc.).  Functionally various personas on FOI FLOW app like IAO Analysts, Ministry level FOI Coordinators can ease their effort while doing document deduplication, document review and redaction on  PII and other confidential data. 

## Architecture and Design
### Architecture
![Here is the Full FOI Flow architecture](./archanddesign/images/Option1_TechArch_Emerald.jpg)

The above architecture diagram describes full architecture of FOI FLOW ( on silver) , with the new Dedupe , NLP Services which will be deployed on BC GOV Emerald Cluster. For the purpose of elaborating Dedupe and related services along with the data storage , please follow below subsection of the above diagram.
![image](https://user-images.githubusercontent.com/78570775/204931018-582b9630-b2be-44ed-9ef2-56d6625668c1.png)

#### Component and module wise description
**EventHub** : This component or tool will be used for purpose of storing persistent event message stream from various Producer components(aka Publisher!) and trigger its corresponding Consumer components(aka Subscriber!) to do related task in a disconnected - loosely coupled manner. All the consumer compoe

### Design
