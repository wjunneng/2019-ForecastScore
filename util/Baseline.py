# -*- coding: utf-8 -*-
"""
@author: shaowu
baseline思路：用第1,2,..,n-1次的成绩，预测第n次的成绩；用第2,..,n次的成绩，预测第n+1次的成绩
这个只是其中的一种思路，希望对入门的有帮助，大佬的话可以忽视了
线上分数：好像8.26左右
"""
import pandas as pd
import numpy as np
from tqdm import *
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import KFold
import xgboost as xgb


def create_feature(data):
    """
    提取特征：
    """
    feats = []
    for i, row in tqdm(data.iterrows()):
        m = [int(i) for i in row['history_score'] if int(i) >= 50]
        # 平均数/中位数/标准差/最大值/最小值/众数/极差/变异系数/  最后两个值的均值/标准差 np.mean(m[-2:]), np.std(m[-2:])
        # 0.89
        # feats.append([np.mean(m), np.median(m), np.std(m), np.max(m), np.min(m), pd.Series(data=m).mode().max(),
        #               np.ptp(m), np.std(m) / np.mean(m), np.mean(m[-2:]), np.std(m[-2:])
        #               ])

        feats.append([np.mean(m), np.median(m), np.std(m), np.max(m), np.min(m), pd.Series(data=m).mode().max(),
                      np.ptp(m), np.std(m) / np.mean(m), m[-2], m[-1]
                      ])

        # feats.append([np.mean(m), np.median(m), np.std(m), np.max(m), np.min(m), np.mean(m[-2:]), np.std(m[-2:])
        #               ])

    feats = pd.DataFrame(feats)
    feats.columns = ['feats{}'.format(i) for i in range(feats.shape[1])]
    return feats


def xgb_model(new_train, y, new_test, lr, N):
    """定义模型"""
    xgb_params = {'booster': 'gbtree',
                  'eta': lr, 'max_depth': 3, 'subsample': 0.8, 'colsample_bytree': 0.8,
                  'objective': 'reg:linear', 'eval_metric': 'rmse',
                  'silent': True,
                  }
    # skf=StratifiedKFold(y,n_folds=5,shuffle=True,random_state=2018)
    skf = KFold(n_splits=N, shuffle=True, random_state=2019)
    oof_xgb = np.zeros(new_train.shape[0])
    prediction_xgb = np.zeros(new_test.shape[0])
    for i, (tr, va) in enumerate(skf.split(new_train, y)):
        print('fold:', i + 1, 'training')
        dtrain = xgb.DMatrix(new_train[tr], y[tr])
        dvalid = xgb.DMatrix(new_train[va], y[va])
        watchlist = [(dtrain, 'train'), (dvalid, 'valid_data')]
        bst = xgb.train(dtrain=dtrain, num_boost_round=30000, evals=watchlist, early_stopping_rounds=500,
                        verbose_eval=400, params=xgb_params)  # ,obj=custom_loss)
        oof_xgb[va] += bst.predict(xgb.DMatrix(new_train[va]), ntree_limit=bst.best_ntree_limit)
        prediction_xgb += bst.predict(xgb.DMatrix(new_test), ntree_limit=bst.best_ntree_limit)
    print("stacking的score: {:<8.8f}".format(np.sqrt(mean_squared_error(oof_xgb, y))))
    prediction_xgb /= N
    return oof_xgb, prediction_xgb


# ====================读入数据==========================================================
train_path = '../data/train_s1/'
test_path = '../data/train_s1/'
all_knowledge = pd.read_csv(train_path + 'all_knowledge.csv')
course1_exams = pd.read_csv(train_path + 'course1_exams.csv')
course2_exams = pd.read_csv(train_path + 'course2_exams.csv')
course3_exams = pd.read_csv(train_path + 'course3_exams.csv')
course4_exams = pd.read_csv(train_path + 'course4_exams.csv')
course5_exams = pd.read_csv(train_path + 'course5_exams.csv')
course6_exams = pd.read_csv(train_path + 'course6_exams.csv')
course7_exams = pd.read_csv(train_path + 'course7_exams.csv')
course8_exams = pd.read_csv(train_path + 'course8_exams.csv')
exam_score = pd.read_csv(train_path + 'exam_score.csv')
student = pd.read_csv(train_path + 'student.csv')
course = pd.read_csv(train_path + 'course.csv')
submission_s1 = pd.read_csv(test_path + 'submission_s1.csv')
# =======================================================================================
'''
简单地构造训练集：第1,2,...n-1次成绩去预测第n次的成绩；第2,...n次成绩去预测第n+1次的成绩；以此类推
'''
test_id = list(set(submission_s1['student_id']))
traindata = []
for stu in tqdm(test_id):
    history_grade = exam_score[exam_score.student_id == stu]
    student_test = submission_s1[submission_s1.student_id == stu]

    for i in range(1, 9):
        m = history_grade[history_grade.course == 'course' + str(i)]['score']
        traindata.append([stu, 'course' + str(i), m.iloc[-1], list(m.iloc[:-1])])
traindata = pd.DataFrame(traindata, columns=['student_id', 'course', 'score', 'history_score'])
print('训练集构造完毕！')

# 方式一
# from util import tool
# traindata = tool.label_encoding(traindata, ['course'])
# 方式二
course_label = dict(zip(['course1', 'course2', 'course3', 'course4', 'course5', 'course6', 'course7', 'course8'],
                        [1, 2, 3, 4, 5, 6, 7, 8]))
traindata['course'] = traindata['course'].map(lambda x: course_label[x])

'''
构造测试集：因为要预测未来两次的成绩，所以预测第n+2次时，是用到第n+1次的结果的
'''
testdata_one = traindata.copy()
testdata_one['history_score'] = testdata_one['history_score'].apply(lambda x: x[1:]) + \
                                testdata_one['score'].apply(lambda x: [x])  # 从第2次成绩开始取,并把第n次的成绩加上
print('第一个测试集构造完毕！')

traindata = pd.concat([traindata, create_feature(traindata)], axis=1)
testdata_one = pd.concat([testdata_one, create_feature(testdata_one)], axis=1)

##########################
# prediction = pd.read_csv('../data/test_s1/submission_s1_sample_xgb.csv')
# prediction = prediction[prediction['exam_id'].isin(['m31I6cTD', 'syfj72xE', 'j8Tva0NC', 'GzBKCNR0', 'DUsu0zkH', 'YTjfkobL', 'u0Yz9rLJ', 'rxoYgBcR'])]
# del prediction['exam_id']
# traindata = pd.merge(traindata, prediction, how='left', on=['student_id', 'course'])
# testdata_one['pred'] = traindata['pred']
##########################

traindata = traindata.merge(student, how='left', on='student_id')
testdata_one = testdata_one.merge(student, how='left', on='student_id')

# 第n次成绩的预测：
traindata = traindata[traindata.score >= 50].reset_index(drop=True)
oof_xgb, prediction_xgb = \
    xgb_model(np.array(traindata.drop(['score', 'history_score'], axis=1)),
              traindata['score'].values,
              np.array(testdata_one.drop(['score', 'history_score'], axis=1)),
              0.01, 5)
testdata_one['score'] = prediction_xgb

print('第二个测试集构造...')
testdata_two = testdata_one[['student_id', 'course', 'score', 'history_score']].copy()  # 注意：加了pred
testdata_two['history_score'] = testdata_two['history_score'].apply(lambda x: x[1:]) + \
                                testdata_one['score'].apply(lambda x: [x])
print('第二个测试集构造完毕！')

testdata_two = pd.concat([testdata_two, create_feature(testdata_two)], axis=1)
testdata_two = testdata_two.merge(student, how='left', on='student_id')

##########################
# del traindata['pred']
# prediction = pd.read_csv('../data/test_s1/submission_s1_sample_xgb.csv')
# prediction = prediction[prediction['exam_id'].isin(['nsEwXu9k', 'Y1UQOByn', 'wzdFr0tP', 'S7V4hIkY', '3SJyhx2F', '3SG49MKN', '7lQGsPpC', 'Vdo50vyP'])]
# del prediction['exam_id']
# traindata = pd.merge(traindata, prediction, how='left', on=['student_id', 'course'])
# testdata_two['pred'] = traindata['pred']
##########################

# 第n+1次成绩的预测：
oof_xgb, prediction_xgb = \
    xgb_model(np.array(traindata.drop(['score', 'history_score'], axis=1)),
              traindata['score'].values,
              np.array(testdata_two.drop(['score', 'history_score'], axis=1)),
              0.01, 5)
testdata_two['score'] = prediction_xgb
# ====================================================================================
# 准备提交数据：因为上面的两次预测不知道是属于哪一个exam_id的，所以做标记
# 倒数第三次考试的exam_id：
num = 3
exam_id1 = [course1_exams['exam_id'].iloc[-num], course2_exams['exam_id'].iloc[-num],
            course3_exams['exam_id'].iloc[-num], course4_exams['exam_id'].iloc[-num],
            course5_exams['exam_id'].iloc[-num], course6_exams['exam_id'].iloc[-num],
            course7_exams['exam_id'].iloc[-num], course8_exams['exam_id'].iloc[-num]]
# 倒数第二次考试的exam_id：
num = 2
exam_id2 = [course1_exams['exam_id'].iloc[-num], course2_exams['exam_id'].iloc[-num],
            course3_exams['exam_id'].iloc[-num], course4_exams['exam_id'].iloc[-num],
            course5_exams['exam_id'].iloc[-num], course6_exams['exam_id'].iloc[-num],
            course7_exams['exam_id'].iloc[-num], course8_exams['exam_id'].iloc[-num]]

# 标记1和2，方便结合数据：
submission_s1['one'] = submission_s1['exam_id'].apply(lambda x: 1 if x in exam_id1 else 2)
print(submission_s1['one'].value_counts())

testdata_one['one'] = 1  # 第一次的预测结果标记为1,即倒数第三次的考试成绩
testdata_two['one'] = 2  # 第二次的预测结果标记为2，即倒数第二次的考试成绩

# 方式二
course_label = dict(zip(
    [1, 2, 3, 4, 5, 6, 7, 8], ['course1', 'course2', 'course3', 'course4', 'course5', 'course6', 'course7', 'course8']
))
testdata_one['course'] = testdata_one['course'].map(lambda x: course_label[x])
testdata_two['course'] = testdata_two['course'].map(lambda x: course_label[x])

result = submission_s1.copy()
result = result.merge(pd.concat([testdata_one, testdata_two], axis=0),
                      how='left', on=['student_id', 'course', 'one'])

result = result[['student_id', 'course', 'exam_id', 'score']]
result.columns = ['student_id', 'course', 'exam_id', 'pred']
result.to_csv('result.csv', index=None, encoding='utf8')