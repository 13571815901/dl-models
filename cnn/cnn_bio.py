# -*- coding: utf-8 -*-
""" Build an Basic ConvNet for training membrane dataset in TensorFlow.

convolutional layer1 + max pooling;
convolutional layer2 + max pooling;
fully connected layer1 + dropout;
fully connected layer2 to prediction.

Derived from: Aymeric Damien
Project: https://github.com/aymericdamien/TensorFlow-Examples/
"""
from __future__ import print_function

import os
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold
# 计算 ACC 混淆矩阵 输出 recall f1等指标
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from sklearn.utils import resample  # 添加 subsampling 工具类

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# Membrane Parameters
N_CLASSES = 5  # CHANGE HERE, total number of classes
DATA_HEIGHT = 2000  # CHANGE HERE, the data height
DATA_WIDTH = 20  # CHANGE HERE, the data width
CHANNELS = 1  # change to 1 if grayscale
DISPLAY_STEP = 10


def get_datasets(dataset_path):
    """读取样本数据集

    Args:
     dataset_path: 数据集路径

    Returns:
     返回样本文件列表及对应分类列表
    """
    sample_paths, sample_labels = list(), list()
    # 获取文件夹下所有数据集文件名
    files = os.listdir(dataset_path)
    for filename in files:
        filepath = os.path.join(dataset_path, filename)
        if os.path.isfile(filepath):
            f = open(filepath, 'r', encoding='utf-8')
            # 读取样本首行分类信息
            m_class_info = f.readline().split()
            f.close()  # sample 文件完整路径
            # 登记相关信息至训练集列表
            sample_paths.append(filepath)
            sample_labels.append(int(m_class_info[1]) - 1)
    return sample_paths, sample_labels


def read_data(file_path):
    """读取样本矩阵信息

    Args:
     file_path: 样本文件名称

    Returns:
     numpy 格式矩阵
    """
    result = list()
    with open(file_path, 'r', encoding='utf-8') as f:
        # 读取首行分类信息
        for line in f.readlines():
            line = line.strip()
            # 过滤首行分类信息和文件末尾空行
            if len(line) > 0 and not line.startswith('>'):
                # 逐行存入矩阵信息
                result.append(line.split())
    # 转换至 numpy array 格式
    mat = np.array(result, dtype=np.float)
    if mat.shape[0] > DATA_HEIGHT:
        # 超出 Max Height 则矩阵做截断
        new_mat = mat[0:DATA_HEIGHT, ]
    else:
        # 矩阵填充 padding with 0
        new_mat = np.lib.pad(mat, ((
            0, DATA_HEIGHT - mat.shape[0]), (0, 0)), 'constant', constant_values=0)
    # 标准化处理
    scale = StandardScaler()
    # 按列 Standardize features by removing the mean and scaling to unit variance
    scale.fit(new_mat)
    # 2-D array 转换为 3-D array [Height, Width, Channel]
    new_mat = scale.transform(new_mat)[:, :, np.newaxis]
    return new_mat


def conv_net(x, n_classes, dropout, reuse, is_training):
    """ 基本卷积神经网络构建

    Args:
     x: 4-D 输入矩阵 [Batch Size, Height, Width, Channel] 在给定的 4-D input 与 filter下计算2D卷积
     n_classes: 输出分类数
     dropout: Dropout 概率
     reuse: 是否应用同样的权重矩阵
     is_training: 网络是否在训练状态

    Returns:
     全连接层输出

    """
    # Define a scope for reusing the variables
    with tf.variable_scope('ConvNet', reuse=reuse):
        """
        data input is a 1-D vector of (DATA_HEIGHT*DATA_WIDTH) features
        Reshape to format [Height x Width x Channel]
        Tensor input become 4-D: [Batch Size, Height, Width, Channel]
        特征矩阵调整为 4-D 输入，-1 代表每次可以自定义样本输入数量
        在给定的 4-D input与 filter下计算2D卷积
        """
        # x = tf.reshape(x, shape=[-1, DATA_HEIGHT, DATA_WIDTH, 1])

        # Convolution Layer 1 with 32 filters and a kernel size of 5
        # 卷积层1：卷积核大小为 5x5，卷积核数量为 32， 激活函数使用 RELU
        conv1 = tf.layers.conv2d(x, 32, 5, activation=tf.nn.relu)
        # Max Pooling (down-sampling) with strides of 2 and kernel size of 2
        # 采用 2x2 维度的最大化池化操作，步长为2
        pool1 = tf.layers.max_pooling2d(conv1, 2, 2)

        # Convolution Layer 2 with 64 filters and a kernel size of 3
        # 卷积层2：卷积核大小为 3x3，卷积核数量为 64， 激活函数使用 RELU
        conv2 = tf.layers.conv2d(pool1, 64, 3, activation=tf.nn.relu)
        # Max Pooling (down-sampling) with strides of 2 and kernel size of 2
        # 采用 2x2 维度的最大化池化操作，步长为2
        pool2 = tf.layers.max_pooling2d(conv2, 2, 2)

        # Flatten the data to a 1-D vector for the fully connected layer
        fc1 = tf.contrib.layers.flatten(pool2)

        # Fully connected layer (in contrib folder for now)
        # 全链接层具有1024神经元
        fc1 = tf.layers.dense(fc1, units=1024)
        # Apply Dropout (if is_training is False, dropout is not applied)
        # 对全链接层的数据加入dropout操作，防止过拟合
        fc1 = tf.layers.dropout(fc1, rate=dropout, training=is_training)

        # Output layer, class prediction
        out = tf.layers.dense(fc1, n_classes)
        # Because 'softmax_cross_entropy_with_logits' already apply softmax,
        # we only apply softmax to testing network
        # 输出层 (Softmax层)，对dropout层的输出Tensor，执行分类操作
        out = tf.nn.softmax(out) if not is_training else out

    return out


def run_model(d_path, l_rate, n_steps, b_size, d_rate, folds, seed=None):
    """运行 CNN 模型

    Args:
      d_path: 数据集路径
      l_rate: 学习率
      n_steps: 训练次数
      b_size: 每次训练取样大小
      k_prob: 训练过程单元保留比例 (Dropout rate)
      folds: 交叉验证次数
      seed: 随机数种子
    """
    # 特征和分类矩阵占位符
    X = tf.placeholder(tf.float32, shape=[None, DATA_HEIGHT, DATA_WIDTH, 1])
    y = tf.placeholder(tf.int32)
    dropout = tf.placeholder(tf.float32)  # dropout (keep probability)

    # Because Dropout have different behavior at training and prediction time, we
    # need to create 2 distinct computation graphs that share the same weights.
    # Create a graph for training
    logits_train = conv_net(X, N_CLASSES, dropout, reuse=False, is_training=True)
    # Create another graph for testing that reuse the same weights
    logits_test = conv_net(X, N_CLASSES, dropout, reuse=True, is_training=False)

    # Define loss and optimizer (with train logits, for dropout to take effect)
    # sparse_softmax_cross_entropy_with_logits() do not use the one hot version of labels
    loss_op=tf.reduce_mean(tf.nn.sparse_softmax_cross_entropy_with_logits(
        logits=logits_train, labels=y))
    optimizer=tf.train.AdamOptimizer(learning_rate=l_rate)
    train_op=optimizer.minimize(loss_op)

    # Evaluate model (with test logits, for dropout to be disabled)
    correct_pred=tf.equal(tf.argmax(logits_train, 1), tf.cast(y, tf.int64))
    accuracy=tf.reduce_mean(tf.cast(correct_pred, tf.float32))

    # Initialize the variables (i.e. assign their default value)
    init=tf.global_variables_initializer()

    # Saver object
    # saver = tf.train.Saver()
    # 读取数据
    traning_set, training_labels = get_datasets(d_path)
    
    # 设定 K-fold 分割器
    rs = KFold(n_splits=folds, shuffle=True, random_state=seed)
    # 生成 k-fold 训练集、验证集索引
    cv_index_set = rs.split(training_labels)
    k_fold_step = 1  # 初始化折数
    # 暂存每次选中的测试集和对应预测结果
    test_cache = pred_cache = np.array([], dtype=np.int)

    # k-fold cross-validation
    for train_index, test_index in cv_index_set:
        # Start training
        with tf.Session(config=tf.ConfigProto(log_device_placement=False)) as sess:

            # Run the initializer
            sess.run(init)
            # 测试集矩阵初始化
            batch_test_x = read_data(traning_set[test_index[0]]).reshape(1, DATA_HEIGHT, DATA_WIDTH, 1)
            batch_test_y = training_labels[test_index[0]]

            for step in range(1, n_steps + 1):
                # 每次选取一定数量样本进行计算
                sample_index = resample(train_index, replace=False, n_samples=b_size)
                batch_x = read_data(traning_set[sample_index[0]]).reshape(1, DATA_HEIGHT, DATA_WIDTH, 1)
                batch_y = training_labels[sample_index[0]]
                for i in sample_index[1:]:
                    batch_x = np.vstack((batch_x, read_data(traning_set[i]).reshape(1, DATA_HEIGHT, DATA_WIDTH, 1)))
                    batch_y = np.hstack((batch_y, training_labels[i]))
                # Run optimization op (backprop)
                sess.run(train_op, feed_dict={
                         X: batch_x, y: batch_y, dropout: d_rate})
                if step % DISPLAY_STEP == 0 or step == 1:
                    # Calculate batch loss and accuracy
                    # 计算ACC时保留所有单元数
                    loss, acc = sess.run([loss_op, accuracy], feed_dict={X: batch_x, y: batch_y, dropout: 0})
                    print("\nTraining Step: {0}, Training Accuracy = {1:.6f}, Batch Loss = {2:.6f}".format(step, acc, loss))

            print("\nTraining Finished!")

            # 测试集评估模型
            for i in test_index[1:]:
                batch_test_x = np.vstack((batch_test_x, read_data(traning_set[i]).reshape(1, DATA_HEIGHT, DATA_WIDTH, 1)))
                batch_test_y = np.hstack((batch_test_y, training_labels[i]))

            lossTest, accTest, predVal = sess.run([loss_op, accuracy, logits_test], feed_dict={
                                                  X: batch_test_x, y: batch_test_y, dropout: 0})

            print("\nFold:", k_fold_step, ", Test Accuracy =", "{:.6f}".format(
                accTest), ", Test Loss =", "{:.6f}".format(lossTest), ", Test Size:", test_index.shape[0])

            # One-hot 矩阵转换为原始分类矩阵
            # argmax_test = batch_test_y
            argmax_pred = np.argmax(predVal, axis=1)
            # 暂存每次选中的测试集和预测结果
            test_cache = np.concatenate((test_cache, batch_test_y))
            pred_cache = np.concatenate((pred_cache, argmax_pred))
        
        print("\n=================================================================================")

        # 每个fold训练结束后次数 +1
        k_fold_step += 1
    
    # 模型评估结果输出
    model_evaluation(N_CLASSES, test_cache, pred_cache)
    # Save your model
    # saver.save(sess, 'membrane_tf_model')
def model_evaluation(num_classes, y_true, y_pred):
    """每个fold测试结束后计算Precision、Recall、ACC、MCC等统计指标
    
    Args:
    num_classes : 分类数
    y_true : array, shape = [n_samples]
        Ground truth (correct) target values.

    y_pred : array, shape = [n_samples]
        Estimated targets as returned by a classifier.
    """
    class_names = []
    pred_names = []
    for i in range(num_classes):
        class_names.append('Class ' + str(i + 1))
        pred_names.append('Pred C' + str(i + 1))

    # 混淆矩阵生成
    cm = confusion_matrix(y_true, y_pred)
    df = pd.DataFrame(data=cm, index=class_names, columns=pred_names)

    # 混淆矩阵添加一列代表各类求和
    df['Sum'] = df.sum(axis=1).values

    print("\n=== Model evaluation ===")
    print("\n=== Accuracy classification score ===")
    print("\nACC = {:.6f}".format(accuracy_score(y_true, y_pred)))
    print("\n=== Matthews Correlation Coefficient ===")
    from .utils import matthews_corrcoef
    print("\nMCC = {:.6f}".format(matthews_corrcoef(cm)))
    print("\n=== Confusion Matrix ===\n")
    print(df.to_string())
    print("\n=== Detailed Accuracy By Class ===\n")
    print(classification_report(y_true, y_pred, target_names=class_names, digits=6))
