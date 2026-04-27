# 第一步：保存网页
通过Safari先打开网页
https://auto.ithome.com
https://www.autor.com.cn

把需要加载的内容都加载到页面，然后通过Safari保存网页归档，将两个网页保存为webarchive文件。

（https://auto.gasgoo.com，这个网站需要手动点击到资讯那个栏目中，然后再保存网页内容)



# 第二步： 抓取新闻
python WebGrep.v00@260406.py ithome.webarchive autor.webarchive
这里的WebGrep脚本通过webarchive网页归档文件，抓取这些网页中的新闻，并且输出到news_output_date_time.txt中
目前只支持ithome和autor两个网站

# 第三部：分析新闻
python AnalysisGrepOutput AnalysisGrepOutput.v00@260406.py news_output_xxx_xxx_analysis.txt
就会使用阿里云千问大模型，对WebGrep脚本抓取出来的news_output文件进行围绕智能驾驶的分析总结。
并生成一个md文件



版本说明
一、260412:
WebGrep.v02@260412.增加了盖世汽车共支持三个网站.py 和 AnalysisGrepOutput.v02@260412.py 是一组
他们很好的支持了ithome、autor、gscn三个网站。
并且在公司ADS PLM群里发了报告，很不错

二、260420:
WebGrep.v03@260420.py 和 AnalysisGrepOutput.v04@260420.支持用户定制提示词.py 是一组
支持用户定制提示词

