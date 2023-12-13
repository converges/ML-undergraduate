# -*- coding: utf-8 -*-
"""Kaggle_Stacking.ipynb

참고자료
    1. [kaggle] https://www.kaggle.com/code/yeonmin/solution
    2. [Youtube] https://www.youtube.com/watch?v=ugICwPuRbLQ

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/15iP148ETqW6dwRhJjdWfHzyRZPde_At7

## Stacking 기법 해석하기
- Stacking Ensemble: Kaggle 같은 대회에서 미세하게 점수를 높이기 위해 사용
- 그동안 다양한 기법들이 누적되어 있어야 사용할 수 있다
- 다양한 Stacking 기법이 있다

## [쉬운 설명]
Stacking: 여러 모델을 쌓아 메타 모델에 넣어 좋은 결과를 얻어낸다!

+ 각 모델들은 그래도 성능이 괜찮은 것들을 모아야 한다
"""

import warnings
warnings.filterwarnings('ignore')

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from tqdm import tqdm_notebook

from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold
# 차원축소: PCA
from sklearn.decomposition import KernelPCA
from sklearn.mixture import GaussianMixture as GMM
from sklearn import svm, neighbors, linear_model, neural_network
from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis

## 새주석: Gradient Boosting 프레임워크
import lightgbm as lgbm

class hist_model(object):

    def __init__(self, bins=50):
        self.bins = bins

    def fit(self, X):

        bin_hight, bin_edge = [], []

        for var in X.T:
            # get bins hight and interval
            bh, bedge = np.histogram(var, bins=self.bins)
            bin_hight.append(bh)
            bin_edge.append(bedge)

        self.bin_hight = np.array(bin_hight)
        self.bin_edge = np.array(bin_edge)

    def predict(self, X):

        scores = []
        for obs in X:
            obs_score = []
            for i, var in enumerate(obs):
                # find wich bin obs is in
                bin_num = (var > self.bin_edge[i]).argmin()-1
                obs_score.append(self.bin_hight[i, bin_num]) # find bin hitght

            scores.append(np.mean(obs_score))

        return np.array(scores)

def run_model(clf_list, train, test, random_state, gmm_init_params='kmeans'):
    ''' ## 새주석: Stacking Ensemble 구현 '''

    ## 새주석: 모델의 개수
    MODEL_COUNT = len(clf_list)

    oof_train = np.zeros((len(train), MODEL_COUNT))
    oof_test = np.zeros((len(test), MODEL_COUNT))
    train_columns = [c for c in train.columns if c not in ['id', 'target', 'wheezy-copper-turtle-magic']]

    for magic in tqdm_notebook(range(512)):
        x_train = train[train['wheezy-copper-turtle-magic'] == magic]
        x_test = test[test['wheezy-copper-turtle-magic'] == magic]
        print("Magic: ", magic, x_train.shape, x_test.shape)

        train_idx_origin = x_train.index
        test_idx_origin = x_test.index

        train_std = x_train[train_columns].std()
        cols = list(train_std.index.values[np.where(train_std >2)])

        x_train = x_train.reset_index(drop=True)
        y_train = x_train.target

        x_train = x_train[cols].values
        x_test = x_test[cols].values

        all_data = np.vstack([x_train, x_test])
        # print("all_data: ", all_data.shape)
        # Kernel PCA
        all_data = KernelPCA(n_components=len(cols), kernel='cosine', random_state=random_state).fit_transform(all_data)

        # GMM
        gmm = GMM(n_components=5, random_state=random_state, max_iter=1000, init_params=gmm_init_params).fit(all_data)
        gmm_pred = gmm.predict_proba(all_data)
        ## 새주석: reshape(-1, _) <- 2번째 인자에 맞춰 정렬하여 알아서 1번째 인자 설정
        gmm_score = gmm.score_samples(all_data).reshape(-1, 1)
        gmm_label = gmm.predict(all_data)

        # hist feature
        hist = hist_model()
        hist.fit(all_data)
        hist_pred = hist.predict(all_data).reshape(-1, 1)

        ## 새주석: GMM(가우시안 혼합 모델) 여러개 추가 -> GMM 예측의 비중을 높인다
        ## 아마 실험적으로 좋은 성능을 내지 않았을까..?
        all_data = np.hstack([all_data, gmm_pred, gmm_pred, gmm_pred, gmm_pred, gmm_pred])

        ## 새주석: 특성추가: 기존. But gmm_score 여러 개 추가 -> 더 큰 가중치
        all_data = np.hstack([all_data, hist_pred, gmm_score, gmm_score, gmm_score])

        # STANDARD SCALER
        all_data = StandardScaler().fit_transform(all_data)

        # new train/test
        x_train = all_data[:x_train.shape[0]]
        x_test = all_data[x_train.shape[0]:]
        # print("data size: ", x_train.shape, x_test.shape)

        ## 새주석: K-Fold Cross validation -> 데이터를 5개로 분류, 비율 유지
        fold = StratifiedKFold(n_splits=5, random_state=random_state)
        for trn_idx, val_idx in fold.split(x_train, gmm_label[:x_train.shape[0]]):
            for model_index, clf in enumerate(clf_list):
                clf.fit(x_train[trn_idx], y_train[trn_idx])
                oof_train[train_idx_origin[val_idx], model_index] = clf.predict_proba(x_train[val_idx])[:,1]

                # 2023/03/02 데이터의 형식이 변경되어, x_test 예측 시 오류 발생하는 것 수정
                if x_test.shape[0] == 0:
                    continue

                #print(oof_test[test_idx_origin, model_index].shape)
                #print(x_test.shape)
                #print(clf.predict_proba(x_test)[:,1])
                oof_test[test_idx_origin, model_index] += clf.predict_proba(x_test)[:,1] / fold.n_splits

    for i, clf in enumerate(clf_list):
        print(clf)
        print(roc_auc_score(train['target'], oof_train[:, i]))
        print()

    oof_train_df = pd.DataFrame(oof_train)
    oof_test_df = pd.DataFrame(oof_test)

    return oof_train_df, oof_test_df

## 새주석: 데이터 로드
os.listdir('../input/instant-gratification/')

## 새주석: 데이터셋 불러오기 1
train = pd.read_csv('../input/instant-gratification/train.csv')
test = pd.read_csv('../input/instant-gratification/test.csv')

## 새주석: Hyperparameters
## SVC, NuSVC =SVM의 일종, 매개변수 nu=오분류와 서포트 벡터의 최대 비율
svnu_params = {'probability':True, 'kernel':'poly','degree':4,'gamma':'auto','nu':0.4,'coef0':0.08, 'random_state':4}
svnu2_params = {'probability':True, 'kernel':'poly','degree':2,'gamma':'auto','nu':0.4,'coef0':0.08, 'random_state':4}
qda_params = {'reg_param':0.111}
svc_params = {'probability':True,'kernel':'poly','degree':4,'gamma':'auto', 'random_state':4}
## 새주석: k-NN hyperparameters
neighbor_params = {'n_neighbors':16}
## 새주석: LR = 로지스틱 회귀
lr_params = {'solver':'liblinear','penalty':'l1','C':0.05,'random_state':42}

## 새주석: 모델은 scikit에서 로드
nusvc_model = svm.NuSVC(**svnu_params)
nusvc2_model = svm.NuSVC(**svnu2_params)
qda_model = QuadraticDiscriminantAnalysis(**qda_params)
svc_model = svm.SVC(**svc_params)
knn_model = neighbors.KNeighborsClassifier(**neighbor_params)
lr_model = linear_model.LogisticRegression(**lr_params)

model_list = [nusvc_model, nusvc2_model, qda_model, svc_model, knn_model, lr_model]
oof_train_kmeans_seed1, oof_test_kmeans_seed1 = run_model(model_list, train, test, 1)
oof_train_kmeans_seed2, oof_test_kmeans_seed2 = run_model(model_list, train, test, 2)
oof_train_random_seed1, oof_test_random_seed1 = run_model(model_list, train, test, 1, 'random')
oof_train_random_seed2, oof_test_random_seed2 = run_model(model_list, train, test, 2, 'random')

## 새주석: 스태킹 앙상블 -> 평균을 1로 맞추어 여러 모델 결합
## train 데이터셋을 기반으로 모델 검증한 결과를 다시 수집
train_second = (oof_train_kmeans_seed1 + oof_train_kmeans_seed2 + oof_train_random_seed1 + oof_train_random_seed2)/4
test_second = (oof_test_kmeans_seed1 + oof_test_kmeans_seed2 + oof_test_random_seed1 + oof_test_random_seed2)/4
print('Ensemble', roc_auc_score(train['target'], train_second.mean(1)))

## 새주석: LightGBM Hyperparameters
lgbm_meta_param = {
        #'bagging_freq': 5,
        #'bagging_fraction': 0.8,
        'min_child_weight':6.790,
        "subsample_for_bin":50000,
        'bagging_seed': 0,
        'boost_from_average':'true',
        'boost': 'gbdt',
        'feature_fraction': 0.450,
        'bagging_fraction': 0.343,
        'learning_rate': 0.025,
        'max_depth': 10, ## 새주석: overfitting 방지
        'metric':'auc',
        'min_data_in_leaf': 78,
        'min_sum_hessian_in_leaf': 8,
        'num_leaves': 18, ## 새주석: overfitting 방지
        'num_threads': 8,
        'tree_learner': 'serial',
        'objective': 'binary',
        'verbosity': 1,
        'lambda_l1': 7.961,
        'lambda_l2': 7.781
        #'reg_lambda': 0.3,
    }

## 새주석: MLP Hyperparameters, tol=허용 오차
mlp16_params = {'activation':'relu','solver':'lbfgs','tol':1e-06, 'hidden_layer_sizes':(16, ), 'random_state':42}

SEED_NUMBER = 4
NFOLD = 5

y_train = train['target']
oof_lgbm_meta_train = np.zeros((len(train), SEED_NUMBER))
oof_lgbm_meta_test = np.zeros((len(test), SEED_NUMBER))
oof_mlp_meta_train = np.zeros((len(train), SEED_NUMBER))
oof_mlp_meta_test = np.zeros((len(test), SEED_NUMBER))

for seed in range(SEED_NUMBER):
    print("SEED Ensemble:", seed)
    mlp16_params['random_state'] = seed
    lgbm_meta_param['seed'] = seed
    folds = StratifiedKFold(n_splits=NFOLD, shuffle=True, random_state=seed)
    for fold_index, (trn_index, val_index) in enumerate(folds.split(train_second, y_train), 1):
        print(f"{fold_index} FOLD Start")
        trn_x, trn_y = train_second.iloc[trn_index], y_train.iloc[trn_index]
        val_x, val_y = train_second.iloc[val_index], y_train.iloc[val_index]

        mlp_meta_model = neural_network.MLPClassifier(**mlp16_params)
        mlp_meta_model.fit(trn_x, trn_y)

        oof_mlp_meta_train[val_index, seed] = mlp_meta_model.predict_proba(val_x)[:,1]
        oof_mlp_meta_test[:, seed] += mlp_meta_model.predict_proba(test_second)[:,1]/NFOLD
        print("MLP META SCORE: ", roc_auc_score(val_y, oof_mlp_meta_train[val_index, seed]))

        # lgbm meta model
        dtrain = lgbm.Dataset(trn_x, label=trn_y, silent=True)
        dcross = lgbm.Dataset(val_x, label=val_y, silent=True)

        lgbm_meta_model = lgbm.train(lgbm_meta_param, train_set=dtrain, valid_sets=[dtrain, dcross],
                                     verbose_eval=False, early_stopping_rounds=100)

        oof_lgbm_meta_train[val_index, seed] = lgbm_meta_model.predict(val_x)
        oof_lgbm_meta_test[:, seed] += lgbm_meta_model.predict(test_second)/NFOLD
        print("LGBM META SCORE: ", roc_auc_score(val_y, oof_lgbm_meta_train[val_index, seed]))

oof_lgbm_meta_train_df = pd.DataFrame(oof_lgbm_meta_train).mean(axis=1).to_frame().rename(columns={0:'lgbm'})
oof_lgbm_meta_test_df = pd.DataFrame(oof_lgbm_meta_test).mean(axis=1).to_frame().rename(columns={0:'lgbm'})
oof_mlp_meta_train_df = pd.DataFrame(oof_mlp_meta_train).mean(axis=1).to_frame().rename(columns={0:'mlp'})
oof_mlp_meta_test_df = pd.DataFrame(oof_mlp_meta_test).mean(axis=1).to_frame().rename(columns={0:'mlp'})

## 새주석: 스태킹 앙상블 -> 평균을 1로 맞추어 여러 모델 결합
## train_second와 LightGBM, MLP 모델 예측 스태킹
oof_train_third = pd.concat([train_second, oof_lgbm_meta_train_df, oof_mlp_meta_train_df], axis=1)
oof_test_third = pd.concat([test_second, oof_lgbm_meta_test_df, oof_mlp_meta_test_df], axis=1)

print('Ensemble', roc_auc_score(train['target'], oof_train_third.mean(1)))

submission = pd.read_csv('../input/instant-gratification/sample_submission.csv')
submission["target"] = oof_test_third.mean(1)
submission.to_csv("submission.csv", index=False)