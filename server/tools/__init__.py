"""工具总表：agent 能干的所有事，一目了然。"""
from .market import (competitor_reverse, keyword_competition, research_asin,
                     research_keyword, traffic_diagnosis)
from .listing import (generate_image, list_generated_images, scrape_product,
                      translate_image)
from .ads import analyze_ads_report, list_report_files
from .lingxing import lingxing_query, lingxing_sellers
from .knowledge import knowledge_search

ALL_TOOLS = [
    # 市场调研
    research_keyword,
    research_asin,
    keyword_competition,
    competitor_reverse,
    traffic_diagnosis,
    # Listing 与图片
    scrape_product,
    generate_image,
    translate_image,
    list_generated_images,
    # 广告诊断
    list_report_files,
    analyze_ads_report,
    # 领星（只读）
    lingxing_sellers,
    lingxing_query,
    # 知识库
    knowledge_search,
]
