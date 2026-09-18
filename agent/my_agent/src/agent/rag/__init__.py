"""RAG 三层知识库。

    loader       文档加载 / PDF 解析
    splitter     文本分块
    embedding    向量化
    vector_store 向量库（Chroma / FAISS）
    retriever    检索（含回退策略）

数据源优先级（高 -> 低）：用户私有上传库 -> 个人学习沉淀库 -> 公共联网兜底。
检索为空时回退公共知识并标注「未找到课件依据」，避免模型编造。
"""
